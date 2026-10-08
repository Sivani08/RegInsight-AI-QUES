"""Rebuildable narrow analytics projection; original evidence stays canonical."""
from sqlalchemy import Table,Column,String,Integer,JSON,select,delete,func,Index
from backend.database.store import metadata,inspections

facts=Table('inspection_analytics',metadata,
    Column('inspection_id',String,primary_key=True),
    *[Column(k,String,index=True) for k in ['company_key','site_key','fei_number','country','product_type','classification','project_area']],
    Column('inspection_year',Integer,index=True),Column('payload',JSON,nullable=False))
versions=Table('retrieval_versions',metadata,Column('id',Integer,primary_key=True),Column('dataset_id',String),Column('version',Integer))
VERSION=1
FIELDS=['company_name','site_name','inspection_date','inspection_type','citation_indicator','observation_count','observation_text','posted_citation_indicator','available_citation_count']

def table_for(store):
    # A lightweight version check prevents reuse after canonical dataset replacement.
    info=store.info() or {}
    if getattr(store,'_retrieval_dataset',None)==info.get('dataset_id') and info.get('dataset_id'):return facts
    return inspections

def attach(store):
    with store.engine.connect() as c:
        version=c.execute(select(versions)).mappings().first()
    info=store.info() or {}
    if version and version['dataset_id']==info.get('dataset_id') and version['version']==VERSION:store._retrieval_dataset=version['dataset_id']

def prepare(store):
    info=store.info()
    if not info:return
    attach(store)
    if table_for(store) is inspections:
        columns=[inspections.c[k] for k in inspections.c.keys() if k!='payload']
        columns += [inspections.c.payload[k].as_string().label(k) for k in FIELDS]
        with store.engine.begin() as writer:
            writer.execute(delete(facts));batch=[];n=0
            stream=writer.execute(select(*columns).execution_options(stream_results=True)).mappings()
            for row in stream:
                row=dict(row);payload={k:row.pop(k) for k in FIELDS}
                for k in ('citation_indicator','observation_count','posted_citation_indicator','available_citation_count'):
                    if payload[k] is not None:payload[k]=int(payload[k])
                batch.append({**row,'payload':payload});n+=1
                if len(batch)>=1000:
                    writer.execute(facts.insert(),batch);batch=[]
                    if n%50000==0:print('Projected',n,'inspection rows',flush=True)
            if batch:writer.execute(facts.insert(),batch)
            assert n==info['valid_records']
            writer.execute(delete(versions));writer.execute(versions.insert().values(id=1,dataset_id=info['dataset_id'],version=VERSION))
        store._retrieval_dataset=info['dataset_id']
        print('Narrow analytics projection ready:',n,flush=True)
    from backend.services.mart import entities_table
    from backend.analytics.dashboard_queries import scoped
    for name,table,columns in [
        ('retrieval_evidence_order',inspections,[inspections.c.inspection_year.desc(),inspections.c.inspection_id]),
        ('retrieval_entity_rank',entities_table,[entities_table.c.kind,entities_table.c.score.desc(),entities_table.c.entity_key]),
        ('retrieval_entity_band',entities_table,[entities_table.c.kind,entities_table.c.band]),
        ('retrieval_scoped_rank',scoped,[scoped.c.scope,scoped.c.score.desc(),scoped.c.site_key]),
        ('retrieval_facts_order',facts,[facts.c.inspection_year.desc(),facts.c.inspection_id])]:
        existing=next((i for i in table.indexes if i.name==name),None)
        (existing if existing is not None else Index(name,*columns)).create(store.engine,checkfirst=True)
    for table in (inspections,facts):
        for field in ('classification','company_key','site_key','country'):
            name='retrieval_'+table.name+'_'+field+'_order'
            existing=next((i for i in table.indexes if i.name==name),None)
            (existing if existing is not None else Index(name,table.c[field],table.c.inspection_year.desc(),table.c.inspection_id)).create(store.engine,checkfirst=True)

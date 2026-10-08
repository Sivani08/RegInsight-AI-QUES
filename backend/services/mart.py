"""Materialized summaries for large exports; source inspection evidence remains in SQL."""
import json
from collections import defaultdict,Counter
from pathlib import Path
from sqlalchemy import Table,Column,String,Float,JSON,select,delete,update
from backend.database.store import metadata,datasets,inspections,Store
from backend.risk.engine import calculate_risk,load_config
from backend.analytics.metrics import metrics,analyze_trend,find_recurring_risks
entities_table=Table('entity_summaries',metadata,Column('entity_id',String,primary_key=True),
    Column('kind',String,index=True),Column('entity_key',String,index=True),Column('company_name',String,index=True),
    Column('score',Float,index=True),Column('band',String,index=True),Column('payload',JSON))
def read_entities(store,kind='site',company=None,search=None,limit=200):
    stmt=select(entities_table.c.payload).where(entities_table.c.kind==kind)
    if company:stmt=stmt.where(entities_table.c.company_name==company)
    if search:stmt=stmt.where(entities_table.c.company_name.icontains(search,autoescape=True))
    stmt=stmt.order_by(entities_table.c.score.desc().nulls_last(),entities_table.c.entity_key).limit(limit)
    with store.engine.connect() as conn:return list(conn.execute(stmt).scalars())
def names(store):
    with store.engine.connect() as conn:return list(conn.execute(select(entities_table.c.company_name).where(entities_table.c.kind=='company')).scalars())
def build(store):
    info=store.info();config=load_config();grouped={'site':defaultdict(list),'company':defaultdict(list)};records=[]
    # Selecting individual JSON fields excludes large source evidence from analytics memory.
    json_fields=['company_name','site_name','inspection_date','citation_indicator','observation_count','observation_text','posted_citation_indicator','available_citation_count']
    columns=[inspections.c[k] for k in ['inspection_id','company_key','site_key','fei_number','country','classification','inspection_year']]
    columns += [inspections.c.payload[k].as_string().label(k) for k in json_fields]
    with store.engine.connect() as conn:
        for row in conn.execute(select(*columns)).mappings():
            r=dict(row)
            for k in ['citation_indicator','observation_count','posted_citation_indicator','available_citation_count']:
                if r[k] is not None:r[k]=int(r[k])
            records.append(r);grouped['site'][r['site_key']].append(r);grouped['company'][r['company_key']].append(r)
    print('Materializing',len(records),'inspections',flush=True)
    bands=Counter();batch=[];top_sites=[];count=0
    with store.engine.begin() as conn:
        conn.execute(delete(entities_table))
        for kind,groups in grouped.items():
            for key,items in groups.items():
                first=max(items,key=lambda r:r['inspection_date'] or '')
                risk=calculate_risk(items,info['as_of'],config)
                entity={'key':key,'company_name':first['company_name'],'site_name':first['site_name'] if kind=='site' else None,
                    'fei_number':first['fei_number'] if kind=='site' else None,'country':', '.join(sorted({r['country'] for r in items if r['country']})),'risk':risk}
                if kind=='site':bands[risk['band']]+=1
                batch.append({'entity_id':kind+':'+key,'kind':kind,'entity_key':key,'company_name':first['company_name'],
                    'score':risk['score'],'band':risk['band'],'payload':entity});count+=1
                if len(batch)>=1000:conn.execute(entities_table.insert(),batch);batch=[]
                if count%25000==0:print('Summaries',count,flush=True)
        if batch:conn.execute(entities_table.insert(),batch)
    recurrence=find_recurring_risks(records)
    # The dashboard only renders totals; full IDs are retrieved in scoped recurrence/evidence calls.
    recurrence=[{**r,'inspection_ids':[]} for r in recurrence]
    trend=analyze_trend(records,info['as_of'],config)
    for y in trend:
        for t in y['recurring_themes']:t['inspection_ids']=[]
    info['mart_ready']=True;info['entity_counts']={k:len(v) for k,v in grouped.items()}
    info['dashboard_cache']={'metrics':metrics(records,info['as_of']),'risk_distribution':{b:bands[b] for b in ['LOW','MODERATE','HIGH','CRITICAL','INSUFFICIENT DATA']},
        'sites':read_entities(store,limit=100),'trend':trend,'recurrence':recurrence,'methodology':config}
    with store.engine.begin() as conn:conn.execute(update(datasets).where(datasets.c.id==1).values(payload=info))
    print('Materialized summaries complete',info['entity_counts'],flush=True)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);a=p.parse_args()
    build(Store())

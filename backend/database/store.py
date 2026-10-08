import hashlib
import json
import logging
import os
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, JSON, select, delete, text, func, update, or_

ROOT=Path(__file__).resolve().parents[2]
metadata=MetaData()
inspections=Table('inspections',metadata,
    Column('inspection_id',String,primary_key=True),
    *[Column(k,String,index=True) for k in ['company_key','site_key','fei_number','country','product_type','classification','project_area']],
    Column('inspection_year',Integer,index=True),Column('payload',JSON,nullable=False))
datasets=Table('dataset',metadata,Column('id',Integer,primary_key=True),Column('payload',JSON,nullable=False))
evidence=Table('evidence',metadata,Column('analysis_id',String,primary_key=True),Column('payload',JSON,nullable=False))

class Store:
    def __init__(self,url=None,allow_fallback=None):
        self.warning=None
        from backend.database.postgres import application_engine
        if url is not None:
            from sqlalchemy.engine import make_url
            if make_url(url).get_backend_name() != 'postgresql':
                raise RuntimeError('PostgreSQL is required')
            self.engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 5})
        else:
            self.engine = application_engine()
        try:
            with self.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
        except Exception:
            raise RuntimeError('PostgreSQL unavailable. Check DATABASE_URL and run migrations.') from None
        self.dialect=self.engine.dialect.name

    def info(self):
        with self.engine.connect() as c:
            return c.execute(select(datasets.c.payload).where(datasets.c.id==1)).scalar_one_or_none()

    def replace(self,records,quality):
        ids=[r['inspection_id'] for r in records]
        if len(set(ids))!=len(ids): raise ValueError('Duplicate inspection IDs in processed data')
        quality=dict(quality)
        quality['dataset_id']=hashlib.sha256(json.dumps(sorted(records,key=lambda r:r['inspection_id']),sort_keys=True,default=str).encode()).hexdigest()[:20]
        indexed=[{'inspection_id':r['inspection_id'],**{k:r.get(k) for k in inspections.c.keys() if k not in ('inspection_id','payload')},'payload':r} for r in records]
        with self.engine.begin() as c:
            c.execute(delete(inspections)); c.execute(delete(datasets))
            for i in range(0,len(indexed),1000): c.execute(inspections.insert(),indexed[i:i+1000])
            c.execute(datasets.insert().values(id=1,payload=quality))
        return quality

    def search(self,limit=None,offset=0,lightweight=False,count_only=False,**filters):
        from backend.database.retrieval_mart import table_for
        inspections=table_for(self) if lightweight or count_only else globals()['inspections']
        fields=['company_name','site_name','inspection_date','citation_indicator','observation_count','observation_text','posted_citation_indicator','available_citation_count']
        columns=[inspections.c[k] for k in ['inspection_id','company_key','site_key','fei_number','country','product_type','classification','project_area','inspection_year']]
        columns += [inspections.c.payload[k].as_string().label(k) for k in fields]
        if lightweight=='recurrence':
            columns=[inspections.c.inspection_id,inspections.c.site_key,inspections.c.country,inspections.c.product_type,inspections.c.inspection_year,inspections.c.payload['observation_text'].as_string().label('observation_text'),inspections.c.payload['company_name'].as_string().label('company_name')]
        statement=select(*columns) if lightweight else select(inspections.c.payload)
        for key,value in filters.items():
            if value is None or value=='': continue
            if key=='company': statement=statement.where(inspections.c.company_key==value.strip().casefold())
            elif key=='site':
                # Resolve indexed identifiers first; a JSON OR forces a full export scan.
                with self.engine.connect() as c:
                    exact=c.execute(select(inspections.c.inspection_id).where(inspections.c.site_key==value).limit(1)).first()
                statement=statement.where(inspections.c.site_key==value if exact else inspections.c.payload['site_name'].as_string()==value)
            elif key=='year': statement=statement.where(inspections.c.inspection_year==int(value))
            elif key=='start_year': statement=statement.where(inspections.c.inspection_year>=int(value))
            elif key=='end_year': statement=statement.where(inspections.c.inspection_year<=int(value))
            elif key in ('start_date','end_date','inspection_type'):
                column=inspections.c.payload['inspection_date' if key != 'inspection_type' else key].as_string()
                statement=statement.where(column>=str(value) if key=='start_date' else column<=str(value) if key=='end_date' else column==value)
            elif key in inspections.c.keys() and key not in ('payload','inspection_id'): statement=statement.where(inspections.c[key]==value)
            else: raise ValueError(f'Unsupported filter: {key}')
        statement=statement.order_by(inspections.c.inspection_year.desc(),inspections.c.inspection_id)
        if count_only:
            statement=statement.with_only_columns(func.count(),maintain_column_froms=True).order_by(None)
            with self.engine.connect() as c:return c.execute(statement).scalar_one()
        if limit is not None: statement=statement.limit(limit).offset(offset)
        with self.engine.connect() as c:
            if not lightweight:return list(c.execute(statement).scalars())
            result=[dict(r) for r in c.execute(statement).mappings()]
            for r in result:
                for key in ['citation_indicator','observation_count','posted_citation_indicator','available_citation_count']:
                    if r.get(key) is not None:r[key]=int(r[key])
            return result

    def save_evidence(self,analysis_id,payload):
        payload=json.loads(json.dumps(payload,default=float))
        with self.engine.begin() as c: c.execute(evidence.insert().values(analysis_id=analysis_id,payload=payload))

    def update_evidence_trace(self,analysis_id,trace):
        with self.engine.begin() as c:
            payload=c.execute(select(evidence.c.payload).where(evidence.c.analysis_id==analysis_id)).scalar_one()
            payload={**payload,'tools':trace}
            c.execute(update(evidence).where(evidence.c.analysis_id==analysis_id).values(payload=payload))

    def get_evidence(self,analysis_id):
        with self.engine.connect() as c: return c.execute(select(evidence.c.payload).where(evidence.c.analysis_id==analysis_id)).scalar_one_or_none()

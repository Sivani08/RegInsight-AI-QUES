"""Explicit QC data contracts, immutable import snapshots and review audit."""
import json,hashlib,uuid,csv,io
from contextlib import contextmanager
from datetime import date,datetime,timezone
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator,field_validator
from data_engineering.intelligence_sources import ROOT
DB = 'quality_control'
class QCRecord(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    study:str=Field(min_length=1,max_length=100)
    site:str=Field(min_length=1,max_length=100)
    month:str
    metric:Literal['etmf_missing','aged_queries','deviations']
    numerator:int=Field(ge=0)
    denominator:int=Field(gt=0)
    @field_validator('month')
    @classmethod
    def month_valid(cls,v):
        if len(v)!=7:raise ValueError('Month must be YYYY-MM')
        date.fromisoformat(v+'-01');return v
    @model_validator(mode='after')
    def counts(self):
        if self.numerator>self.denominator:raise ValueError('Numerator exceeds denominator')
        return self
class ImportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    name:str=Field(min_length=1,max_length=200)
    kind:Literal['demo','real']
    records:list[QCRecord]=Field(min_length=1,max_length=10000)
class ReviewRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    dataset_id:str
    signal_id:str
    actor:str=Field(min_length=1,max_length=100)
    action:Literal['approve','edit','dismiss','escalate']
    note:str=Field(min_length=1,max_length=2000)
def connection(path=None):
    from backend.database.postgres import connection as postgres_connection
    if path is not None and str(path) != DB:
        raise ValueError('QC storage requires PostgreSQL')
    return postgres_connection(DB)

def now():return datetime.now(timezone.utc).isoformat()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def ingest(body,method='manual',source='user-supplied'):
    unique={};duplicates=0
    for r in body.records:
        key=(r.study,r.site,r.month,r.metric);value=r.model_dump()
        if key in unique:
            if unique[key]!=value:raise ValueError('Conflicting counts for study/site/month/metric; import rejected')
            duplicates+=1
        unique[key]=value
    records=sorted(unique.values(),key=lambda r:(r['study'],r['site'],r['month'],r['metric']))
    content={'kind':body.kind,'records':records};identifier=digest(content)[:24]
    meta={'id':identifier,'name':body.name,'kind':body.kind,'sha256':digest(content),'created_at':now(),'connection_method':method,'source':source,'records':len(records),'duplicate_rows':duplicates,'studies':sorted({r['study'] for r in records}),'min_month':min(r['month'] for r in records),'max_month':max(r['month'] for r in records)}
    with connection() as c:
        old=c.execute('SELECT payload FROM datasets WHERE id=%s',(identifier,)).fetchone()
        if not old:
            c.execute('INSERT INTO datasets VALUES (%s,%s)',(identifier,json.dumps(meta)))
            c.cursor().executemany('INSERT INTO records VALUES (%s,%s,%s)',[(identifier,digest(r)[:24],json.dumps(r)) for r in records])
        event={'type':'import','dataset_id':identifier,'method':method,'source':source,'duplicate_rows':duplicates,'reused_snapshot':bool(old)}
        c.execute('INSERT INTO audit VALUES (%s,%s,%s)',(str(uuid.uuid4()),now(),json.dumps(event)))
    return {**(json.loads(old[0]) if old else meta),'reused_snapshot':bool(old)}
def datasets():
    with connection() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM datasets ORDER BY storage_sequence DESC')]
def rows(dataset_id,study=None):
    with connection() as c:
        meta=c.execute('SELECT payload FROM datasets WHERE id=%s',(dataset_id,)).fetchone()
        if not meta:raise ValueError('Unknown QC dataset')
        result=[{'record_id':r['id'],**json.loads(r['payload'])} for r in c.execute('SELECT id,payload FROM records WHERE dataset_id=%s',(dataset_id,))]
    return json.loads(meta[0]),[r for r in result if not study or r['study']==study]
def csv_import(text,name,kind):
    if len(text.encode())>2000000:raise ValueError('CSV exceeds 2 MB')
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')));items=[]
    if set(reader.fieldnames or [])!=set(QCRecord.model_fields):raise ValueError('CSV columns must be study,site,month,metric,numerator,denominator')
    for i,r in enumerate(reader):
        if i>=10000:raise ValueError('Maximum 10000 rows')
        for k in ('numerator','denominator'):r[k]=int(r[k])
        items.append(QCRecord.model_validate(r))
    return ingest(ImportRequest(name=name,kind=kind,records=items))
def review(body,signal):
    with connection() as c:
        event={**body.model_dump(),'type':'review','signal_snapshot':signal,'identity_assurance':'authenticated account'}
        identifier=str(uuid.uuid4());stamp=now()
        c.execute('INSERT INTO audit VALUES (%s,%s,%s)',(identifier,stamp,json.dumps(event)))
    return {'id':identifier,'created_at':stamp,**event}
def audit(dataset_id):
    with connection() as c:return [{'id':r['id'],'created_at':r['created_at'],**json.loads(r['payload'])} for r in c.execute("SELECT * FROM audit WHERE (payload::jsonb ->> 'dataset_id')=%s ORDER BY storage_sequence DESC LIMIT 200",(dataset_id,))]

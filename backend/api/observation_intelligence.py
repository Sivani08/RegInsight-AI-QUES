"""Typed read APIs and explicit bounded tagging jobs; no remote AI on startup."""
import json,uuid,os
from typing import Literal
from functools import lru_cache
from fastapi import APIRouter,Query,HTTPException,Request,Header
from backend.api.identity import principal,reviewer
from backend.database.postgres import connection
from backend.workflows.jobs import enqueue
from pydantic import Field
from backend.genai.contracts import StrictModel,ObservationTag,TagsPage,MetricsPage,GroupsPage
from backend.genai.classifier import Classifier
from backend.services import observation_intelligence as s
from data_engineering.intelligence_sources import db
router=APIRouter(prefix='/api/observations')
@lru_cache(maxsize=2)
def single_request_gate(enabled):
    # Process-lifetime budget/rate window shared by single-item API calls.
    from backend.genai.request_gate import RequestGate
    return RequestGate(enabled=enabled)
class ClassifyRequest(StrictModel):
    observation_text:str=Field(min_length=1,max_length=20000)
    provider:Literal['gemini','ollama','rules','mock','local','openai','claude']=Field(default_factory=lambda:os.getenv('AI_PROVIDER','gemini'))
    model:str|None=None
    enable_ai:bool=False
class BatchRequest(StrictModel):
    dataset:str='all'
    provider:Literal['gemini','ollama','rules','mock','local','openai','claude']=Field(default_factory=lambda:os.getenv('AI_PROVIDER','gemini'))
    model:str|None=None
    enable_ai:bool=False
    batch_size:int=Field(default=250,ge=1,le=2000)
    max_requests:int=Field(default=20,ge=0,le=100)
class Job(StrictModel):
    id:str
    status:str
    run_id:str|None=None
    error:str|None=None
@router.post('/classify',response_model=ObservationTag)
def classify(body:ClassifyRequest):
    from backend.services.intelligence_lock import run_lock
    with run_lock(s.DB):
        with db() as c:
            return s.classify_cached(body.observation_text,Classifier(body.provider,body.model,body.enable_ai,gate=single_request_gate(body.enable_ai)),c)
@router.post('/batch-tag',response_model=Job,status_code=202)
def batch(body:BatchRequest,request:Request,idempotency_key:str|None=Header(None,max_length=100)):
    actor=reviewer(request)
    with connection() as current:
        identifier=enqueue(current,actor.user_id,None,body.model_dump(),
            'classify:'+actor.user_id+':'+(idempotency_key or str(uuid.uuid4())),'classification')
    return Job(id=identifier,status='queued')
@router.get('/jobs/{identifier}',response_model=Job)
def job(identifier:str,request:Request):
    actor=principal(request)
    with connection() as c:
        r=c.execute('SELECT id,status,result_reference,error FROM background_jobs WHERE id=%s AND (user_id=%s OR %s)',
            (identifier,actor.user_id,actor.role in ('reviewer','admin'))).fetchone()
    if not r:raise HTTPException(404,'Job not found')
    return Job(id=r['id'],status=r['status'].lower(),run_id=r['result_reference'],error=r['error'])
@router.get('/tags',response_model=TagsPage)
def tags(run_id:str|None=None,company:str|None=None,site:str|None=None,year:int|None=None,theme:str|None=None,severity:str|None=None,dataset:str|None=None,grain:str='inspection',product:str|None=None,inspection_type:str|None=None,observation_id:str|None=None,group_id:str|None=None,review_required:bool|None=None,limit:int=Query(25,ge=1,le=200),offset:int=Query(0,ge=0)):
    return s.tags(**locals())
@router.get('/themes',response_model=MetricsPage)
@router.get('/severity',response_model=MetricsPage)
@router.get('/recurrence',response_model=MetricsPage)
def metrics(run_id:str|None=None,company:str|None=None,site:str|None=None,year:int|None=None,start_year:int|None=None,end_year:int|None=None,theme:str|None=None,severity:str|None=None,dataset:str|None=None,grain:str='inspection',product:str|None=None,inspection_type:str|None=None,group_id:str|None=None,review_required:bool|None=None,group_by:str='theme'):
    return s.metrics(**locals())
@router.get('/similar/{observation_id}',response_model=TagsPage)
def similar(observation_id:str,run_id:str|None=None,grain:str='inspection',limit:int=Query(20,ge=1,le=50)):
    return s.similar(**locals())
@router.get('/groups',response_model=GroupsPage)
def groups(run_id:str|None=None,dataset:str|None=None,grain:str='inspection',company:str|None=None,site:str|None=None,year:int|None=None,theme:str|None=None,severity:str|None=None,group_id:str|None=None,review_required:bool|None=None,limit:int=Query(20,ge=1,le=200),offset:int=Query(0,ge=0)):
    return s.groups(**locals())
@router.get('/quarantine')
def quarantine(limit:int=Query(25,ge=1,le=200),offset:int=Query(0,ge=0)):
    with db() as c:
        total=c.execute('SELECT count(*) FROM quarantine').fetchone()[0]
        records=[{'id':r['id'],'reason':r['reason'],'source_record':json.loads(r['payload'])} for r in c.execute('SELECT * FROM quarantine ORDER BY id LIMIT %s OFFSET %s',(limit,offset))]
    return {'total':total,'records':records,'offset':offset}
@router.get('/report')
def report():
    from data_engineering.intelligence_sources import ROOT
    current=s.latest()
    path=ROOT/'data/intelligence/latest/report.json'
    if path.exists():
        try:
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved.get('id')==current['id']:return saved
        except (ValueError,OSError):pass
    return s.report(current['id'])
@router.get('/inventory')
def inventory():
    from data_engineering.intelligence_sources import ROOT
    path=ROOT/'data/intelligence/inventory.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'files':[]}

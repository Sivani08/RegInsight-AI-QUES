from fastapi import APIRouter,Query,HTTPException,Request
from backend.api.identity import reviewer
from pydantic import BaseModel,Field
from backend.services import observations as s
from backend.analytics.observation_rubric import CATEGORIES,SEVERITIES,RUBRIC
from backend.analytics.taxonomy import THEMES
router=APIRouter(prefix='/api/observation-workspace')
@router.get('')
def workspace(run_id:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(12,ge=1,le=100)):
    try:run=s.get_run(run_id)
    except ValueError:return {'available':False,'categories':CATEGORIES,'severities':SEVERITIES,'themes':list(THEMES),'rubric':RUBRIC}
    data=s.rows(run['id'])
    return {'available':True,'run':run,'rows':data[offset:offset+limit],'total':len(data),'summary':s.summaries(run['id']),'categories':CATEGORIES,'severities':SEVERITIES,'themes':list(THEMES),'rubric':RUBRIC}
@router.post('/demo')
def demo():return s.run_batch()
@router.get('/export')
def export(run_id:str):return {'run':s.get_run(run_id),'rows':s.rows(run_id),'summary':s.summaries(run_id)}
@router.get('/history')
def history(run_id:str,observation_id:str):
    import json
    with s.connect() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM reviews WHERE run_id=%s AND observation_id=%s ORDER BY storage_sequence',(run_id,observation_id))]
class Review(BaseModel):
    run_id:str
    observation_id:str
    version:int=Field(ge=1)
    reviewer:str=Field(min_length=1,max_length=100)
    note:str=Field(min_length=1,max_length=2000)
    category:str
    themes:list[str]
    severity:str
    evidence_quotes:list[str]
@router.post('/review')
def review(body:Review,request:Request):
    actor=reviewer(request)
    try:return s.review(body.run_id,body.observation_id,{k:getattr(body,k) for k in ['category','themes','severity','evidence_quotes']},body.version,actor.user_id,body.note)
    except ValueError as e:raise HTTPException(409 if 'changed' in str(e) else 400,str(e))

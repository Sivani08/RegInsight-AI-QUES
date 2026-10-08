from fastapi import APIRouter, Request, HTTPException
from pydantic import Field
from backend.workflows.schemas import WorkflowRequest, ReviewDecision, Strict
from backend.workflows.repository import Conflict
from backend.api.identity import principal, reviewer

router=APIRouter(prefix='/api/workflows',tags=['Auditable AI workflows'])

def service(request):
    if request.app.state.workflows is None:
        raise HTTPException(503,'AI workflow service unavailable. Check the local embedding model and restart the service.')
    return request.app.state.workflows

def get(request,identifier):
    try:
        state=service(request).repository.get(identifier)
        actor=principal(request)
        if state.user_id!=actor.user_id and actor.role not in ('reviewer','admin'):
            raise HTTPException(404,'Workflow not found')
        return state
    except KeyError:raise HTTPException(404,'Workflow not found') from None

@router.post('',status_code=202)
def create(body:WorkflowRequest,request:Request):
    s=service(request);state=s.create(body,principal(request))
    return state

@router.get('/reviews/pending')
def pending(request:Request):return service(request).repository.pending(principal(request))

@router.get('/configuration')
def configuration(request:Request):
    s=service(request)
    return {'policy':s.policy.model_dump(),'indexed_chunks':s.retrieval.repository.count(),
        'embedding_type':'local Ollama semantic embeddings',
        'vector_store':'PostgreSQL pgvector exact cosine and full-text rank fusion',
        'review_identity':'authenticated PostgreSQL account'}

@router.get('/{identifier}')
def read(identifier:str,request:Request):return get(request,identifier)

@router.get('/{identifier}/trace')
def trace(identifier:str,request:Request):
    state=get(request,identifier)
    return {'workflow_id':identifier,'request_id':state.request_id,'query':state.request.question,
        'routing':state.routing,'retrieval':state.retrieval_trace,'retrieval_history':state.retrieval_history,'tools':state.tool_results,
        'agents':state.agent_outputs,'artifacts':state.artifacts,'reviews':state.reviews,
        'status':state.status,'final_response':state.final_response,'events':service(request).repository.events(identifier)}

@router.get('/{identifier}/retrieval')
def retrieval(identifier:str,request:Request):return get(request,identifier).retrieval_trace

@router.get('/{identifier}/evaluation')
def evaluation(identifier:str,request:Request):return [a.evaluation for a in get(request,identifier).artifacts]

@router.post('/{identifier}/resume',status_code=202)
def resume(identifier:str,request:Request):
    state=get(request,identifier)
    if state.status not in ('REVISION_REQUIRED','APPROVED'):raise HTTPException(409,'Workflow is not resumable')
    from backend.database.postgres import connection
    from backend.workflows.jobs import enqueue
    if not state.reviews:
        raise HTTPException(409,'A persisted review decision is required')
    review_id=state.reviews[-1]['review_id']
    with connection() as current:
        enqueue(current,state.user_id,identifier,{'review_id':review_id},'resume:'+review_id)
    return state

@router.post('/{identifier}/reviews/{action}')
def review(identifier:str,action:str,body:ReviewDecision,request:Request):
    get(request,identifier)
    actions={'approve':'APPROVE','modify':'MODIFY','revision':'REJECT','reject':'REJECT'}
    if action not in actions:raise HTTPException(404,'Unknown review action')
    try:state=service(request).review(identifier,actions[action],body,reviewer(request))
    except Conflict as e:raise HTTPException(409,str(e)) from None
    return state

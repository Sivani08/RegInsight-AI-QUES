from fastapi import APIRouter,Request
from pydantic import BaseModel,Field
from backend.agents.investigator import InspectionAgent
router=APIRouter()
class AgentQuestion(BaseModel):
    question:str=Field(min_length=1,max_length=2000)
    company:str|None=None
    site:str|None=None
    observation_text:str|None=Field(default=None,max_length=20000)
@router.post('/api/agent/query')
def query(request:Request,body:AgentQuestion):
    return InspectionAgent(request.app.state.service).query(**body.model_dump())
@router.get('/api/agent/tools')
def tools():
    from backend.tools.observation_tools import ObservationTools
    # Expose the executable registry so added tools cannot disappear from discovery.
    return {name:schema.model_json_schema()
            for name,(schema,_) in ObservationTools(None).registry.items()}

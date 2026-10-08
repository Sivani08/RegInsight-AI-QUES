from fastapi import APIRouter
from pydantic import BaseModel,Field
from backend.genai.providers import analyze_observation
router=APIRouter()
class ObservationInput(BaseModel):
    observation_text:str=Field(min_length=1,max_length=20000)
@router.post('/api/observations/analyze')
def observation(body:ObservationInput):
    return analyze_observation(body.observation_text)

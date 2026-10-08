"""Observation tools reuse existing validation/trace mechanics, with typed outputs."""
from pydantic import Field
from backend.genai.contracts import StrictModel
from backend.tools.registry import Tools
from backend.services import observation_intelligence as s
class IntelligenceArgs(StrictModel):
    run_id:str|None=None
    company:str|None=None
    site:str|None=None
    theme:str|None=None
    severity:str|None=None
    start_year:int|None=None
    end_year:int|None=None
    observation_id:str|None=None
    group_id:str|None=None
    review_required:bool|None=None
    dataset:str|None=None
    grain:str='inspection'
class GroupArgs(IntelligenceArgs):
    group_by:str='theme'
    limit:int=Field(default=200,ge=1,le=1000)
class SimilarArgs(StrictModel):
    observation_id:str
    run_id:str|None=None
    grain:str='inspection'
class ObservationTools(Tools):
    def __init__(self,service):
        super().__init__(service)
        self.registry.update({'get_observation_tags':(IntelligenceArgs,lambda **kw:s.tags(**kw).model_dump()),'find_recurring_themes':(GroupArgs,lambda **kw:s.metrics(**kw).model_dump()),'get_severity_distribution':(IntelligenceArgs,lambda **kw:s.metrics(**kw).model_dump()),'get_theme_trend':(IntelligenceArgs,lambda **kw:s.metrics(group_by='year',limit=1000,**kw).model_dump()),'get_company_observation_intelligence':(IntelligenceArgs,lambda **kw:s.metrics(**kw).model_dump()),'get_site_observation_intelligence':(IntelligenceArgs,lambda **kw:s.metrics(**kw).model_dump()),'find_similar_observations':(SimilarArgs,lambda **kw:s.similar(**kw).model_dump())})
        self.registry.update({'get_semantic_groups':(IntelligenceArgs,lambda **kw:s.groups(**kw).model_dump()),'get_review_observations':(IntelligenceArgs,lambda **kw:s.tags(**{**kw,'review_required':True}).model_dump())})

import os
from datetime import date
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .catalog import METRICS, DIMENSIONS, FOCUSES, INTENTS
MAX_QUESTION = min(4000,int(os.getenv('DASHBOARD_MAX_QUESTION','4000')))
MAX_HISTORY = min(12,int(os.getenv('DASHBOARD_MAX_HISTORY','12')))
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Filters(Strict):
    company:str|None=Field(None,max_length=200)
    site:str|None=Field(None,max_length=200)
    fei_number:str|None=Field(None,max_length=100)
    country:str|None=Field(None,max_length=100)
    product_type:str|None=Field(None,max_length=150)
    project_area:str|None=Field(None,max_length=150)
    inspection_type:str|None=Field(None,max_length=150)
    classification:Literal['NAI','VAI','OAI','Unknown']|None=None
    year:int|None=Field(None,ge=1900,le=2100)
    start_year:int|None=Field(None,ge=1900,le=2100)
    end_year:int|None=Field(None,ge=1900,le=2100)
    start_date:date|None=None
    end_date:date|None=None
    theme:str|None=Field(None,max_length=150)
    severity:Literal['Low','Medium','High','Critical','Unclassified']|None=None
    risk_band:Literal['LOW','MODERATE','HIGH','CRITICAL','INSUFFICIENT DATA']|None=None
    semantic_group:str|None=Field(None,max_length=200)
    dataset:Literal['real','demo','synthetic']|None=None
    grain:Literal['inspection']|None=None
    @model_validator(mode='after')
    def range_valid(self):
        if self.start_year and self.end_year and self.start_year>self.end_year:raise ValueError('Invalid year range')
        if self.start_date and self.end_date and self.start_date>self.end_date:raise ValueError('Invalid date range')
        if self.year and (self.start_year or self.end_year):raise ValueError('Use year or a year range, not both')
        return self
class Turn(Strict):
    role:Literal['user','assistant']
    content:str=Field(max_length=MAX_QUESTION)
class Context(Strict):
    analysis_id:str|None=Field(None,max_length=64)
class QueryRequest(Strict):
    question:str=Field(min_length=1,max_length=MAX_QUESTION)
    focus:str='overall_dashboard'
    filters:Filters=Field(default_factory=Filters)
    history:list[Turn]=Field(default_factory=list,max_length=MAX_HISTORY)
    context:Context=Field(default_factory=Context)
    limit:int=Field(10,ge=1,le=50)
    offset:int=Field(0,ge=0,le=1000000)
    @field_validator('focus')
    @classmethod
    def focus_known(cls,v):
        if v not in FOCUSES:raise ValueError('Unknown dashboard focus')
        return v
    @field_validator('question')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():raise ValueError('Question cannot be blank')
        return v.strip()
class QueryPlan(Strict):
    intent:str
    focus:str
    metrics:list[str]=Field(min_length=1,max_length=18)
    dimensions:list[str]=Field(default_factory=list,max_length=5)
    filters:Filters=Field(default_factory=Filters)
    comparison:Literal['previous_period']|None=None
    limit:int=Field(10,ge=1,le=50)
    offset:int=Field(0,ge=0,le=1000000)
    @model_validator(mode='after')
    def supported(self):
        if self.intent not in INTENTS or self.focus not in FOCUSES:raise ValueError('Unknown intent or focus')
        if any(m not in METRICS for m in self.metrics):raise ValueError('Unsupported metric')
        if any(d not in DIMENSIONS for d in self.dimensions):raise ValueError('Unsupported dimension')
        obs=self.focus in ('observation_intelligence','recurring_risk_signals')
        values=self.filters.model_dump(exclude_none=True)
        if not obs and any(k in values for k in ('theme','severity','semantic_group','dataset','grain')):
            raise ValueError('Observation filters require an observation focus')
        if obs and any(k in values for k in ('country','product_type','project_area','classification','inspection_type','start_date','end_date','risk_band')):
            raise ValueError('That filter is not available in the observation snapshot; select inspection analytics or clear it.')
        if not obs and any(m in ('observation_count','severity_distribution','review_required_count','recurring_themes','recurrence_count') for m in self.metrics):
            raise ValueError('Observation metrics require the observation snapshot')
        if obs and any(m not in ('observation_count','severity_distribution','review_required_count','recurring_themes','recurrence_count') for m in self.metrics):
            raise ValueError('Inspection metrics cannot use the observation snapshot as their denominator')
        if 'risk_score' in self.metrics and self.intent=='risk_explanation' and not any([self.filters.site,self.filters.company,self.filters.fei_number]):
            raise ValueError('Select a site or company, or ask for highest risk sites first.')
        return self
class Insight(Strict):
    type:Literal['fact','pattern','limitation']
    statement:str
    metrics:dict[str,Any]=Field(default_factory=dict)
class Layers(Strict):
    scope:dict[str,Any]
    metrics:dict[str,Any]
    patterns:dict[str,Any]
    context:dict[str,Any]
    evidence_and_limitations:dict[str,Any]
class QueryResponse(Strict):
    question:str
    semantic_plan:QueryPlan
    headline:str
    insights:list[Insight]
    layers:Layers
    supporting_data:list[dict[str,Any]]=Field(max_length=50)
    suggested_questions:list[str]=Field(min_length=2,max_length=4)
    context:Context
    evidence_id:str
    mode:Literal['deterministic']='deterministic'
    total:int=0
    offset:int=0
    limit:int=10

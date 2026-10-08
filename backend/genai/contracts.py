from datetime import datetime,timezone
from typing import Literal,Annotated
from pydantic import BaseModel,ConfigDict,Field,ValidationInfo,model_validator
from backend.analytics.intelligence_taxonomy import THEME_NAMES,VERSION
class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class Classification(StrictModel):
    category:Literal['Quality and compliance','Unclassified']
    theme:Literal[THEME_NAMES]
    severity:Literal['Low','Medium','High','Critical','Unclassified']
    confidence:float=Field(ge=0,le=1)
    evidence_quote:str=Field(min_length=1,max_length=1000)
    rationale:str=Field(min_length=1,max_length=1500)
    keywords:list[Annotated[str,Field(min_length=1,max_length=120)]]=Field(max_length=30)
    @model_validator(mode='after')
    def consistent(self,info:ValidationInfo):
        if (self.theme=='Unclassified')!=(self.category=='Unclassified'):raise ValueError('Unclassified category/theme must agree')
        if self.severity=='Unclassified' and self.theme!='Unclassified':raise ValueError('Unclassified severity requires an unclassified theme')
        if info.context and 'observation_text' in info.context:self.verify_evidence(info.context['observation_text'])
        return self
    def verify_evidence(self,text):
        if not self.evidence_quote.strip() or self.evidence_quote not in text:raise ValueError('Evidence must occur verbatim in normalized observation')
        if any(not k.strip() or k.lower() not in text.lower() for k in self.keywords):raise ValueError('Keywords must occur in observation')
        from backend.analytics.intelligence_taxonomy import supported_theme,severity_supported,is_instruction
        import re
        contexts=[]
        for match in re.finditer(re.escape(self.evidence_quote),text):
            at=match.start()
            contexts.append(text[max(text.rfind('.',0,at),text.rfind('!',0,at),text.rfind('?',0,at))+1:match.end()])
        if self.theme!='Unclassified' and not any(not is_instruction(sentence) and supported_theme(self.theme,sentence) for sentence in contexts):raise ValueError('Evidence context does not support classification')
        if re.search(r'(?:risk score|patient (?:harm|death)|FDA (?:determined|concluded))',self.rationale,re.I):raise ValueError('Rationale contains a prohibited conclusion')
        if is_instruction(self.evidence_quote) and self.theme!='Unclassified':raise ValueError('Instructions are not classification evidence')
        if not supported_theme(self.theme,self.evidence_quote):raise ValueError('Theme lacks supporting evidence')
        if not severity_supported(self.severity,self.evidence_quote):raise ValueError('Severity lacks supporting evidence')
        return self
class ObservationTag(Classification):
    inspection_id:Annotated[str,Field(max_length=512)]|None=None
    observation_id:Annotated[str,Field(max_length=512)]|None=None
    dataset:Annotated[str,Field(max_length=512)]|None=None
    source:Literal['rules','mock','gemini','ollama','local','openai','claude']
    provider:Literal['rules','mock','gemini','ollama','local','openai','claude']|None=None
    model:str=Field(max_length=512)
    taxonomy_version:str=Field(default=VERSION,max_length=80)
    prompt_version:str=Field(default='2.0',max_length=80)
    reviewed:bool=False
    ai_generated:bool=True
    fallback:bool=False
    raw_status:str=Field(default='validated',max_length=80)
    review_status:Literal['Human review required','Reviewed']='Human review required'
    timestamp:str=Field(default_factory=lambda:datetime.now(timezone.utc).isoformat(),max_length=64)
    @model_validator(mode='after')
    def provenance(self):
        if self.provider is None:self.provider=self.source
        if self.provider!=self.source:raise ValueError('Provider and source must agree')
        if datetime.fromisoformat(self.timestamp).tzinfo is None:raise ValueError('Timestamp needs a timezone')
        return self
# Public descriptive name; the existing tag contract remains the single schema.
ObservationClassification=ObservationTag
class ObservationRecord(StrictModel):
    observation_id:str
    inspection_id:str|None
    observation_hash:str
    dataset:str
    grain:Literal['inspection','annual_template']
    company:str|None=None
    site:str|None=None
    fiscal_year:int|None=None
    product:str|None=None
    inspection_type:str|None=None
    observation_text:str
    original_text:str
    source_observation_id:str|None=None
    source_file:str
    source_sheet:str|None=None
    source_row:str|None=None
    frequency:int|None=None
    tag:ObservationTag
    observation_group_id:str
    similarity_score:float
    grouping_method:str
    embedding_model:str|None=None
    embedding_version:str|None=None
    origins:list[dict]=Field(default_factory=list)
class TagsPage(StrictModel):
    run_id:str
    total:int
    records:list[ObservationRecord]
class SemanticGroup(StrictModel):
    group_id:str
    observation_count:int=Field(ge=0)
    unique_texts:int=Field(ge=0)
    inspection_count:int=Field(ge=0)
    companies:int=Field(ge=0)
    sites:int=Field(ge=0)
    representative_id:str
    grouping_method:str
class GroupsPage(StrictModel):
    run_id:str
    total:int=Field(ge=0)
    groups:list[SemanticGroup]
class ThemeMetric(StrictModel):
    theme:str
    year:int|None=None
    company:str|None=None
    site:str|None=None
    product:str|None=None
    inspection_type:str|None=None
    observation_count:int
    inspection_count:int
    unique_sites:int
    recurrence_score:float
    severity_distribution:dict[str,int]
    frequency_sum:int|None=None
class MetricsPage(StrictModel):
    run_id:str
    grain:str
    groups:list[ThemeMetric]
    total_groups:int=0
    returned_limit:int=200
    ai_severity_index:float|None
    ai_severity_observations:int
    notice:str='AI-derived observation severity index; excluded from deterministic risk scores.'

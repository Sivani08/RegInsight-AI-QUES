from pydantic import BaseModel,ConfigDict,Field
from backend.genai.providers import analyze_observation

class Filters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    company:str|None=None
    site:str|None=None
    fei_number:str|None=None
    product_type:str|None=None
    country:str|None=None
    year:int|None=None
    classification:str|None=None
    start_year:int|None=None
    end_year:int|None=None

class TrendArgs(Filters):
    theme:str|None=None

class RecurrenceArgs(Filters):
    group_by:str|None=None

class ObservationArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    observation_text:str=Field(min_length=1,max_length=20000)

class EvidenceArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    analysis_id:str

class Tools:
    def __init__(self,service):
        self.service=service
        self.trace=[]
        self.registry={
            'search_inspections':(Filters,self.search_inspections),
            'calculate_risk':(Filters,self.calculate_risk),
            'analyze_trend':(TrendArgs,self.analyze_trend),
            'find_recurring_risks':(RecurrenceArgs,self.find_recurring_risks),
            'analyze_observation':(ObservationArgs,analyze_observation),
            'get_evidence':(EvidenceArgs,self.get_evidence)}

    def call(self,name,**arguments):
        if name not in self.registry: raise ValueError('Unknown agent tool')
        schema,fn=self.registry[name]
        args=schema.model_validate(arguments).model_dump(exclude_none=True)
        item={'tool':name,'arguments':{k:v for k,v in args.items() if k!='observation_text'},'status':'running'}
        if 'observation_text' in args: item['input_characters']=len(args['observation_text'])
        self.trace.append(item)
        try:
            result=fn(**args)
            item['status']='complete'
            if isinstance(result,list): item['result_count']=len(result)
            return result
        except Exception:
            item['status']='failed'
            raise

    def search_inspections(self,**filters): return self.service.store.search(**filters)
    def calculate_risk(self,**filters): return self.service.risk(**filters)
    def analyze_trend(self,**filters): return self.service.trend(**filters)
    def find_recurring_risks(self,**filters): return self.service.recurrence(**filters)
    def get_evidence(self,analysis_id):
        result=self.service.store.get_evidence(analysis_id)
        if result is None: raise ValueError('Evidence analysis not found')
        return result

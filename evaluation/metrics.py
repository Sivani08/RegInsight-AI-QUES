"""Offline DeepEval metrics for the deterministic RegInsight retrieval pipeline.

These measure factual contracts, not subjective LLM answer quality.
"""
import json
import math
from deepeval.metrics import BaseMetric

class ContractMetric(BaseMetric):
    def __init__(self,kind):
        self.kind=kind;self.threshold=1.0;self.async_mode=False
        self.include_reason=True;self.verbose_mode=False;self.evaluation_model='deterministic-local'

    @property
    def __name__(self):return self.kind

    def measure(self,test_case,*args,**kwargs):
        self.error=None
        try:
            actual=json.loads(test_case.actual_output);expected=json.loads(test_case.expected_output)
            records=actual['records'];ids=[r['inspection_id'] for r in records];gold=expected['ids']
            if self.kind=='Numeric agreement':
                checks=[k in actual['metrics'] and actual['metrics'][k]==v for k,v in expected['metrics'].items()]
                score=sum(checks)/len(checks) if checks else 0
            elif self.kind=='Retrieval precision':
                score=len(set(ids)&set(gold))/len(ids) if ids else float(not gold)
            elif self.kind=='Retrieval recall':
                score=len(set(ids)&set(gold))/len(gold) if gold else float(not ids)
            elif self.kind=='Evidence grounding':
                sources={r['inspection_id']:r for r in map(json.loads,test_case.retrieval_context or [])}
                checks=[r['inspection_id'] in sources and all(r.get(k)==sources[r['inspection_id']].get(k)
                    for k in ('quote','company','site','classification','inspection_date')) for r in records]
                score=sum(checks)/len(checks) if checks else float(not gold)
            elif self.kind=='Scope correctness':
                score=float(actual['filters']==expected['filters'] and actual['offset']==expected['offset'])
            elif self.kind=='Latency budget':
                elapsed=actual['elapsed_ms'];budget=expected['budget_ms']
                score=float(isinstance(elapsed,(int,float)) and math.isfinite(elapsed) and 0<=elapsed<=budget)
            else:raise ValueError('Unknown metric')
            self.score=score;self.success=score>=self.threshold
            self.reason=f'{self.kind}: {score:.3f}; required {self.threshold:.3f}.'
            if self.kind=='Latency budget':self.reason+=f' Measured {elapsed:.2f} ms; budget {budget} ms.'
        except (KeyError,TypeError,ValueError,ZeroDivisionError) as exc:
            self.score=0.;self.success=False;self.reason=f'Missing or invalid evaluation contract: {type(exc).__name__}.'
        return self.score

    async def a_measure(self,test_case,*args,**kwargs):return self.measure(test_case)
    def is_successful(self):return self.success is True

KINDS=['Numeric agreement','Retrieval precision','Retrieval recall','Evidence grounding','Scope correctness','Latency budget']

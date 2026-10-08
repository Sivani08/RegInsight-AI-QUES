"""Run actual DeepEval locally against independently collected retrieval cases."""
import os
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT']='1'
os.environ['DEEPEVAL_DISABLE_DOTENV']='1'
os.environ['DEEPEVAL_NO_INSPECT_PROMPT']='1'
os.environ['CONFIDENT_TRACE_FLUSH']='false'
import json,sys,copy,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
# Evaluation is offline. A configured remote service must never receive these cases.
def no_network(*args,**kwargs):raise RuntimeError('Offline evaluation: network access disabled')
socket.socket.connect=no_network;socket.socket.connect_ex=no_network
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.evaluate.configs import AsyncConfig,DisplayConfig,CacheConfig
from deepeval.test_run import global_test_run_manager
from evaluation.metrics import ContractMetric,KINDS

def run():
    source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'evaluation/cases.json'
    payload=json.loads(source.read_text(encoding='utf-8'))
    cases=[LLMTestCase(**c) for c in payload['cases']]
    global_test_run_manager.reset();global_test_run_manager.disable_request=True
    results=evaluate(cases,[ContractMetric(k) for k in KINDS],
        _skip_reset=True,async_config=AsyncConfig(run_async=False),cache_config=CacheConfig(write_cache=False,use_cache=False),
        display_config=DisplayConfig(show_indicator=False,print_results=False,inspect_after_run=False))
    # Deliberately incorrect answers prove each gate rejects regressions.
    faults=[]
    base=next(c for c in cases if json.loads(c.actual_output)['records'])
    for kind in KINDS:
        values=base.model_dump();a=json.loads(values['actual_output'])
        if kind=='Numeric agreement':a['metrics']['total_inspections']+=1
        elif kind=='Retrieval precision':a['records'].append({'inspection_id':'fabricated'})
        elif kind=='Retrieval recall':a['records']=a['records'][1:]
        elif kind=='Evidence grounding':a['records'][0]['quote']='Fabricated evidence'
        elif kind=='Scope correctness':a['filters']={'year':1900}
        elif kind=='Latency budget':a['elapsed_ms']=1000000
        values['actual_output']=json.dumps(a);metric=ContractMetric(kind);metric.measure(LLMTestCase(**values))
        faults.append({'metric':kind,'rejected':not metric.is_successful()})
    report={'framework':'DeepEval','version':__import__('importlib.metadata').metadata.version('deepeval'),
        'mode':'offline deterministic custom metrics; no LLM judge','dataset_id':payload['dataset_id'],
        'cases':[{'name':r.name,'passed':r.success,'metrics':[{'name':m.name,'score':m.score,'passed':m.success,'reason':m.reason} for m in r.metrics_data]} for r in results.test_results],
        'negative_controls':faults}
    target=ROOT/'docs/deepeval-report.json';target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Report:',target)
    if not all(r['passed'] for r in report['cases']) or not all(r['rejected'] for r in faults):raise SystemExit(1)
if __name__=='__main__':run()

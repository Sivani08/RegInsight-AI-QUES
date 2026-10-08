"""Check the live chatbot against the application's calculated evidence."""
import json,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
results=[]
with httpx.Client(trust_env=False,timeout=90) as client:
    for question in ['What stands out in this dashboard?','What is the OAI rate?']:
        start=time.perf_counter();events=[]
        with client.stream('POST','http://127.0.0.1:8021/api/chatbot/stream',json={'question':question}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:events.append(json.loads(line))
        final=events[-1];evidence=next((v for v in events if v['type']=='evidence'),{})
        result={'question':question,'answer':final,'sources':evidence.get('sources',[]),
                'wall_seconds':round(time.perf_counter()-start,2)}
        print(json.dumps({'question':question,**final}),flush=True);results.append(result)
(ROOT/'docs/chatbot-data-check.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
assert all(r['answer'].get('mode')=='local_llm' for r in results),'A live question did not produce a validated local-model answer.'

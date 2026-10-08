import json,re,threading,time
from contextvars import ContextVar
from collections import deque
import httpx
from backend.agents.chatbot import local_origin

_gate=threading.BoundedSemaphore(1)
_last_call=ContextVar('workflow_model_call',default=None)

class StructuredLLM:
    """Loopback-only schema client. Each judge invocation is an actual model call."""
    def __init__(self,timeout=120): self.timeout=timeout;self.calls=deque(maxlen=100)

    @property
    def last_call(self):return _last_call.get()

    def generate(self,model,system,payload,schema,purpose):
        if not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,150}',model) or 'cloud' in model.casefold():raise ValueError('Downloaded local model required')
        raw=json.dumps(payload,ensure_ascii=False)
        if len(raw)>60000:raise ValueError('Prompt context exceeds local bound')
        if not _gate.acquire(blocking=False):raise RuntimeError('Local workflow model busy; retry later')
        started=time.monotonic()
        try:
            with httpx.Client(trust_env=False,timeout=httpx.Timeout(self.timeout,connect=3)) as client:
                r=client.post(local_origin()+'/api/chat',json={'model':model,'stream':False,'think':False,
                    'messages':[{'role':'system','content':system},{'role':'user','content':raw}],
                    'format':schema.model_json_schema(),'options':{'temperature':0,'num_ctx':8192,'num_predict':1800},'keep_alive':'10m'})
                r.raise_for_status();data=r.json()
            if not data.get('done') or data.get('done_reason')=='length':raise ValueError('Incomplete local model output')
            result=schema.model_validate_json(data['message']['content'])
            call={'purpose':purpose,'model':model,'latency_ms':round((time.monotonic()-started)*1000),
                'output_tokens':data.get('eval_count'),'prompt_tokens':data.get('prompt_eval_count')}
            self.calls.append(call);_last_call.set(call)
            return result
        finally:_gate.release()

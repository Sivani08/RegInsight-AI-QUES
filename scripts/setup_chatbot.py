"""Register a local domain-configured model; no weight training or remote API."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.agents.chatbot import SYSTEM,MODEL,local_origin
import httpx

def main():
    prompt=SYSTEM+'\nWhen no sources are supplied, request RegInsight evidence rather than answering from memory.'
    (ROOT/'config/RegInsight.Modelfile').write_text('FROM qwen3:1.7b\nPARAMETER temperature 0\nPARAMETER num_ctx 4096\nPARAMETER num_predict 240\nSYSTEM """'+prompt+'"""\n',encoding='utf-8')
    origin=local_origin()
    with httpx.Client(trust_env=False,timeout=120) as client:
        tags=client.get(origin+'/api/tags');tags.raise_for_status()
        if 'qwen3:1.7b' not in {m['name'] for m in tags.json()['models']}:
            raise SystemExit('Download the Apache-2.0 base model first: ollama pull qwen3:1.7b')
        response=client.post(origin+'/api/create',json={'model':MODEL,'from':'qwen3:1.7b',
            'system':prompt,'parameters':{'temperature':0,'num_ctx':4096,'num_predict':240},'stream':False})
        response.raise_for_status()
        print('Registered '+MODEL+'. Domain-configured, not fine-tuned.')
if __name__=='__main__':main()

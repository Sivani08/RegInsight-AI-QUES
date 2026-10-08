import asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.agents.chatbot import RegInsightChatAgent
from backend.semantic.models import QueryRequest

async def main():
    agent=RegInsightChatAgent(None)
    print(json.dumps(await agent.status()),flush=True)
    results=[]
    for question in ['What does OAI mean?','How does RegInsight detect recurring risks?','Is this model trained on our data?']:
        values=[v async for v in agent.stream(QueryRequest(question=question))]
        result={'question':question,**values[-1]};results.append(result)
        print(json.dumps(result),flush=True)
    (ROOT/'docs/chatbot-live-check.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
asyncio.run(main())

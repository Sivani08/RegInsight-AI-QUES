import asyncio,json
import pytest
from pg_client import TestClient
from backend.agents.chatbot import RegInsightChatAgent,local_origin,model_name
from backend.api.main import create_app
from backend.database.store import Store
from backend.database.load import load
from backend.services.intelligence import Intelligence
from backend.semantic.models import QueryRequest

@pytest.fixture
def agent():
    store=Store();load(store=store)
    return RegInsightChatAgent(Intelligence(store))

def events(agent,question):
    async def collect():return [v async for v in agent.stream(QueryRequest(question=question))]
    return asyncio.run(collect())

def test_definition_retrieves_classification_source(agent):
    result=agent.retrieve(QueryRequest(question='What does OAI mean?'))
    assert result['sources'][0]['id']=='K2'
    assert result['analytics'] is None

def test_unknown_question_does_not_invent_evidence(agent):
    assert not agent.retrieve(QueryRequest(question='Write a birthday limerick'))['sources']

def test_how_it_works_is_methodology_not_live_metrics(agent):
    result=agent.retrieve(QueryRequest(question='How does RegInsight detect recurring risks?'))
    assert result['analytics'] is None
    assert 'K4' in [s['id'] for s in result['sources']]

def test_dashboard_scope_and_context(agent):
    body=QueryRequest(question='How many inspections are in the portfolio?',filters={'classification':'OAI'})
    result=agent.retrieve(body)
    assert result['sources'][0]['id']=='D1'
    assert result['analytics']['semantic_plan']['filters']['classification']=='OAI'
    assert result['analytics']['layers']['metrics']['total_inspections']>=0

def test_rate_question_uses_actual_data(agent):
    result=agent.retrieve(QueryRequest(question='What is the OAI rate?'))
    assert result['analytics'] is not None
    source=json.loads(result['sources'][0]['text'])
    rate=result['analytics']['layers']['metrics']['oai_rate']
    assert source['requested_metrics']['oai_rate_percent']==f'{rate*100:.2f}%'
    assert source['records']==[]
    assert 'components' not in result['sources'][0]['text']
    assert any('OAI inspections out of' in a for a in source['allowed_answers'])

def test_numeric_semantics_cannot_be_rewritten(agent):
    result=agent.retrieve(QueryRequest(question='What is the OAI rate?'))
    choices=json.loads(result['sources'][0]['text'])['allowed_answers']
    good={'answer':choices[0],'citations':['D1']}
    assert agent.validate(json.dumps(good),result['sources'])==good
    with pytest.raises(ValueError):
        agent.validate(json.dumps({'answer':'The rate measures high-risk locations.','citations':['D1']}),result['sources'])

def test_regulatory_overclaim_rejected():
    with pytest.raises(ValueError):
        RegInsightChatAgent.validate('{"answer":"OAI means an action is required.","citations":["K2"]}',[{'id':'K2','text':'OAI recommends regulatory action.'}])

def test_unknown_citations_and_numbers_rejected():
    sources=[{'id':'D1','text':json.dumps({'allowed_answers':['There are 12 inspections.']})}]
    for value in [{'answer':'There are 13 inspections.','citations':['D1']},
                  {'answer':'There are 12 inspections.','citations':['D9']},
                  {'answer':'There are 12 inspections.','citations':[]}]:
        with pytest.raises(ValueError):RegInsightChatAgent.validate(json.dumps(value),sources)
    assert RegInsightChatAgent.validate('{"answer":"There are 12 inspections.","citations":["D1"]}',sources)['citations']==['D1']

def test_evidence_precedes_llm_answer(agent,monkeypatch):
    async def generate(body,sources):return {'answer':'OAI means Official Action Indicated.','citations':['K2']},{'first_token_ms':5}
    monkeypatch.setattr(agent,'generate',generate)
    result=events(agent,'What does OAI mean?')
    assert [e['type'] for e in result]==['status','evidence','status','answer']
    assert result[-1]['mode']=='local_llm'

def test_model_failure_is_honest_fallback(agent,monkeypatch):
    async def generate(*args):raise ValueError('bad output')
    monkeypatch.setattr(agent,'generate',generate)
    result=events(agent,'What does OAI mean?')
    assert result[-1]['mode']=='evidence_only'
    assert result[-1]['model'] is None

def test_busy_model_does_not_queue(agent):
    async def collect():
        async with agent.gate:return [v async for v in agent.stream(QueryRequest(question='What does OAI mean?'))]
    assert asyncio.run(collect())[-1]['mode']=='evidence_only'

@pytest.mark.parametrize('url',['https://example.com','http://127.0.0.1:11434/private','http://u:p@localhost','http://localhost?x=1'])
def test_loopback_only(monkeypatch,url):
    monkeypatch.setenv('CHAT_OLLAMA_URL',url)
    with pytest.raises(ValueError):local_origin()

def test_cloud_model_rejected(monkeypatch):
    monkeypatch.setenv('CHAT_MODEL','qwen-cloud')
    with pytest.raises(ValueError):model_name()

def test_api_security_and_limits(agent,monkeypatch):
    async def generate(*args):return {'answer':'OAI means Official Action Indicated.','citations':['K2']},{}
    monkeypatch.setattr(RegInsightChatAgent,'generate',generate)
    with TestClient(create_app(agent.service.store)) as client:
        assert client.post('/api/chatbot/stream',json={'question':'x'*4001}).status_code==422
        assert client.post('/api/chatbot/stream',json={'question':'OAI'},headers={'Origin':'https://evil.example'}).status_code==403
        response=client.post('/api/chatbot/stream',json={'question':'What does OAI mean?'})
        assert response.status_code==200
        assert [json.loads(line) for line in response.text.splitlines()][-1]['mode']=='local_llm'

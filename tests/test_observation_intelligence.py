import json
import pytest,httpx
from pathlib import Path
from backend.genai.contracts import Classification,ObservationTag
from backend.genai.classifier import Classifier
from backend.genai.request_gate import RequestGate,RequestLimit
from backend.analytics.intelligence_taxonomy import rules,VERSION
from backend.analytics.observation_groups import Grouper
from data_engineering.intelligence_sources import db,add
from backend.services import observation_intelligence as service
TEXT='Original laboratory records were not retained after testing.'
@pytest.fixture
def good():return {'category':'Quality and compliance','theme':'Data Integrity','severity':'High','confidence':.8,'evidence_quote':'records were not retained','rationale':'Failure to retain original records supports this classification.','keywords':['records']}
@pytest.mark.parametrize('update',[{'extra':'bad'},{'severity':'Urgent'},{'confidence':1.01},{'confidence':-.1},{'confidence':'0.8'},{'theme':'Invented'},{'category':'Invented'},{'evidence_quote':''},{'rationale':''}])
def test_strict_invalid(good,update):
    with pytest.raises(ValueError):Classification.model_validate({**good,**update})
def test_valid_and_invented_evidence(good):
    assert Classification.model_validate(good).verify_evidence(TEXT).severity=='High'
    with pytest.raises(ValueError):Classification.model_validate({**good,'evidence_quote':'not in source'}).verify_evidence(TEXT)
def test_empty_and_negation():
    with pytest.raises(ValueError):Classifier().classify('  ')
    assert Classifier().classify('No evidence of data integrity failures.').theme=='Unclassified'
@pytest.mark.parametrize('error',[TimeoutError('secret-key'),json.JSONDecodeError('secret','',0),ValueError('secret')])
def test_failures_fallback(caplog,error):
    c=Classifier('gemini',enable_ai=True)
    class Fake:
        def analyze(self,text):raise error
    c.provider=Fake();r=c.classify(TEXT)
    assert r.fallback and not r.ai_generated and r.source=='rules'
    assert 'secret' not in caplog.text

def test_gate_off_and_budget():
    gate=RequestGate(enabled=False)
    with pytest.raises(RequestLimit):gate.acquire()
    gate=RequestGate(enabled=True,max_requests=1);gate.acquire()
    with pytest.raises(RequestLimit):gate.acquire()

def test_retry_and_rate_limit(monkeypatch):
    client=httpx.Client;calls=[];sleeps=[]
    def handler(request):
        calls.append(1)
        return httpx.Response(429,headers={'retry-after':'2'}) if len(calls)==1 else httpx.Response(200,json={'ok':True})
    monkeypatch.setattr(httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(handler)))
    gate=RequestGate(enabled=True,max_requests=2,rate=30,sleep=sleeps.append,clock=lambda:0)
    assert gate.request('https://example.invalid',{}, {},1)=={'ok':True}
    assert gate.requests==2 and sum(sleeps)>=2

def test_timeout_retries_count_toward_budget(monkeypatch):
    client=httpx.Client
    def handler(request):raise httpx.ReadTimeout('secret')
    monkeypatch.setattr(httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(handler)))
    gate=RequestGate(enabled=True,max_requests=2,sleep=lambda _:None,clock=lambda:0)
    with pytest.raises(RequestLimit):gate.request('https://example.invalid',{}, {},1)
    assert gate.requests==2

def test_long_cooldown_stops(monkeypatch):
    client=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(lambda r:httpx.Response(429,headers={'retry-after':'120'}))))
    gate=RequestGate(enabled=True,sleep=lambda _:None)
    with pytest.raises(RequestLimit):gate.request('https://example.invalid',{}, {},1)
    assert gate.requests==1 and gate.disabled

@pytest.fixture
def corpus(tmp_path):
    path='intelligence';stats={'source_observation_rows':0,'duplicate_observation_rows':0,'empty_text_rows':0,'conflicting_records':0}
    with db(path) as c:
        for i in range(3):
            r={'dataset':'real','grain':'inspection','inspection_id':str(i),'text':TEXT,'metadata':{'company':'Test Co','site':'SITE-1','year':2023+i,'date':f'{2023+i}-01-01'},'source':{'file':'test.csv','row':str(i+2)}}
            add(c,r,stats);add(c,r,stats)
        add(c,{'dataset':'annual','grain':'annual_template','inspection_id':None,'text':TEXT,'frequency':100,'metadata':{'year':2025},'source':{'file':'annual.xlsx','row':'2'}},stats)
        c.execute('INSERT INTO corpus VALUES (%s,%s)',('quality',json.dumps(stats)))
    return path

def test_cache_batch_recurrence_and_annual_separation(corpus):
    first=service.run(path=corpus,batch_size=1);second=service.run(path=corpus,batch_size=2)
    assert first['total']==4 and first['unique_texts']==1 and first['cache_hits']==0
    assert second['cache_hits']==1 and second['api_requests']==0
    m=service.metrics(path=corpus);r=m.groups[0]
    assert r.observation_count==3 and r.inspection_count==3 and r.recurrence_score==pytest.approx(2/3,abs=1e-6)
    annual=service.metrics(path=corpus,grain='annual_template').groups[0]
    assert annual.inspection_count==0 and annual.frequency_sum==100
    assert m.ai_severity_index is None
    assert len(service.similar(service.tags(path=corpus).records[0].observation_id,path=corpus).records)==2

def test_cache_version_and_provider_isolation(corpus):
    service.run(path=corpus)
    fallback=service.run(path=corpus,provider='gemini',enable_ai=False)
    assert fallback['cache_hits']==0 and fallback['fallbacks']==4 and fallback['api_requests']==0
    with pytest.raises(ValueError):service.run(path=corpus,taxonomy_version='unknown')

def test_conflicts_preserved(tmp_path):
    stats={'source_observation_rows':0,'duplicate_observation_rows':0,'empty_text_rows':0,'conflicting_records':0}
    with db('intelligence') as c:
        for company in ['First','Second']:
            add(c,{'dataset':'real','grain':'inspection','inspection_id':'same','observation_id':'obs','text':'CAPA failed '+company,'metadata':{'company':company,'date':'2025-01-01'},'source':{'file':'example','row':company}},stats)
        assert c.execute('SELECT count(*) FROM conflicts').fetchone()[0]>=1
        assert c.execute('SELECT count(*) FROM observations').fetchone()[0]==2

def test_local_group_cosine():
    g=Grouper(threshold=.7)
    a=g.assign('a','laboratory records testing retained','Data Integrity')
    b=g.assign('b','laboratory records testing retained original','Data Integrity')
    assert a[0]==b[0] and b[1]>=.7 and b[2]=='lexical_cosine'

def test_risk_unchanged_between_providers(corpus):
    from backend.database.store import Store
    from backend.database.load import load
    from backend.services.intelligence import Intelligence
    store=Store();load(store=store);engine=Intelligence(store)
    before=engine.risk(company='Aster Therapeutics')
    service.run(path=corpus,provider='rules');service.run(path=corpus,provider='gemini',enable_ai=False)
    assert engine.risk(company='Aster Therapeutics')==before

def test_gemini_payload_strict_schema(good):
    from backend.genai.providers import GeminiProvider
    p=GeminiProvider();p.key='not-real';p.model='gemini-2.5-flash-lite';p.structured=True;seen={}
    def request(url,payload,headers):
        seen.update(url=url,payload=payload)
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(good)}]}}]}
    p.request=request
    assert Classification.model_validate(p.analyze(TEXT)).verify_evidence(TEXT)
    assert seen['payload']['generationConfig']['responseJsonSchema']['additionalProperties'] is False
    assert 'not-real' not in seen['url']

def test_api_end_to_end(corpus,monkeypatch):
    from pg_client import TestClient
    from backend.api.main import create_app
    from backend.database.store import Store
    from backend.api import observation_intelligence as routes
    original=db
    monkeypatch.setattr(service,'db',lambda path=corpus:original(corpus))
    monkeypatch.setattr(routes,'db',lambda path=corpus:original(corpus))
    service.run(path=corpus)
    with TestClient(create_app(Store())) as c:
        result=c.get('/api/observations/tags',params={'limit':1}).json()
        assert result['total']==3 and len(result['records'])==1
        oid=result['records'][0]['observation_id']
        assert c.get('/api/observations/similar/'+oid).status_code==200
        assert c.get('/api/observations/recurrence').json()['groups'][0]['inspection_count']==3
        tag=c.post('/api/observations/classify',json={'observation_text':TEXT,'provider':'rules'}).json()
        assert tag['source']=='rules' and tag['evidence_quote'] in TEXT
        assert c.post('/api/observations/classify',json={'observation_text':TEXT,'risk_score':99}).status_code==422
        job=c.post('/api/observations/batch-tag',json={'provider':'rules','max_requests':0}).json()
        assert c.get('/api/observations/jobs/'+job['id']).json()['status']=='completed'

def test_raw_discovery_and_missing_metadata(tmp_path):
    from data_engineering.intelligence_sources import ingest
    root=tmp_path/'project';(root/'data/raw').mkdir(parents=True)
    (root/'data/raw/one.csv').write_text('inspection_id,observation_text,company_name\nA,CAPA failed,Sample\n',encoding='utf-8')
    (root/'data/raw/two.csv').write_text('inspection_id,observation_text,company_name\nB,Records were deleted,Sample\n',encoding='utf-8')
    path='intelligence';quality=ingest(root,path)
    assert not quality['unsupported_inputs']
    with db(path) as c:
        assert c.execute("SELECT count(*) FROM observations WHERE dataset='additional'").fetchone()[0]==2
        assert c.execute("SELECT year FROM observations WHERE inspection_id='A'").fetchone()[0] is None
        assert c.execute("SELECT count(*) FROM texts").fetchone()[0]<quality['total_observations']

def test_run_lock(tmp_path):
    from backend.services.intelligence_lock import run_lock
    with run_lock(tmp_path/'db'):
        with pytest.raises(ValueError):
            with run_lock(tmp_path/'db'):pass
    with run_lock(tmp_path/'db'):pass

def test_all_imported_sources_after_batch():
    from data_engineering.intelligence_sources import DB
    if not DB.exists():pytest.skip('Real corpus not installed')
    try:r=service.latest()
    except ValueError:pytest.skip('First real tagging run still in progress')
    if r.get('dataset')!='all':pytest.skip('Requires an all-source tagging run; the supplied snapshot is real-only')
    with db() as c:
        counts={row['dataset']:row['n'] for row in c.execute('SELECT dataset,count(*) n FROM observations GROUP BY dataset')}
        if 'real' not in counts:pytest.skip('Supplied real corpus not installed')
        assert counts['real']==280114 and counts['annual']==4696 and counts['demo']==72
        assert c.execute("SELECT sum(frequency) FROM observations WHERE grain='annual_template'").fetchone()[0]==41286
        assert c.execute('SELECT count(*) FROM origins').fetchone()[0]>=284999
    assert r['total']==284983 and r['unique_texts']==22027 and r['api_requests']==0

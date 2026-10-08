import json
from datetime import date
import pytest,httpx
from pg_client import TestClient
from backend.services import qc_data as d,qc_signals as s,qc_connections as conn,knowledge as kb
from backend.api.main import create_app
from backend.database.store import Store
@pytest.fixture
def database(tmp_path,monkeypatch):
    monkeypatch.setattr(d,'DB','quality_control')
    return tmp_path

def records(n=8):
    return [d.QCRecord(study='S1',site='SITE1',month=f'2025-{i+1:02}',metric='etmf_missing',numerator=3+i*3,denominator=100) for i in range(n)]
def imported():return d.ingest(d.ImportRequest(name='fixture',kind='demo',records=records()))
def test_import_idempotent_and_conflicts(database):
    a=imported();b=imported();assert a['id']==b['id'] and b['reused_snapshot']
    assert len(d.rows(a['id'])[1])==8
    bad=records();bad.append(bad[0].model_copy(update={'numerator':20}))
    with pytest.raises(ValueError):d.ingest(d.ImportRequest(name='bad',kind='real',records=bad))
    assert len(d.datasets())==1
@pytest.mark.parametrize('update',[{'denominator':0},{'numerator':101},{'month':'2026-13'},{'metric':'random'},{'numerator':'3'},{'invented':1}])
def test_invalid_records(update):
    with pytest.raises(ValueError):d.QCRecord.model_validate({**records(1)[0].model_dump(),**update})
def test_csv_validation_and_dedup(database):
    text='study,site,month,metric,numerator,denominator\nS1,A,2026-01,aged_queries,2,10\nS1,A,2026-01,aged_queries,2,10\n'
    r=d.csv_import(text,'test','demo');assert r['records']==1 and r['duplicate_rows']==1
    with pytest.raises(ValueError):d.csv_import('wrong\n1','bad','real')
def test_forecast_chronology_and_baseline():
    series=[{'month':f'2025-{i+1:02}','rate':.1+i*.02} for i in range(8)]
    r=s.forecast(series,'2025-09-01');assert r['method']=='linear_trend' and r['backtest_folds']==5
    assert r['points'][0]['rate']==pytest.approx(.26)
    # Current/future rows cannot alter fit or backtest.
    assert s.forecast(series+[{'month':'2025-09','rate':1.}], '2025-09-01')==r
    assert s.forecast(series[:5],'2025-09-01')['status']=='insufficient_history'
    assert s.forecast(series[:2]+series[3:],'2025-09-01')['status']=='missing_periods'
    constant=[{**v,'rate':.2} for v in series]
    assert s.forecast(constant,'2025-09-01')['method']=='last_value'
def test_signals_and_review_trace(database):
    a=imported();report=s.analyze(a['id'],as_of='2025-09-01');signal=report['signals'][0]
    assert signal['numerator']==24 and signal['denominator']==100
    assert len(signal['evidence_ids'])==8 and signal['review_required']
    event=d.review(d.ReviewRequest(dataset_id=a['id'],signal_id=signal['id'],actor='Reviewer',action='edit',note='Check filing plan first'),signal)
    assert event['signal_snapshot']['id']==signal['id']
    assert d.audit(a['id'])[0]['note']=='Check filing plan first'
    assert s.analyze(a['id'],study='missing')['signals']==[]
def test_api_connector_config_and_payload(database,monkeypatch):
    config=database/'connections.json';config.write_text(json.dumps({'connections':[{'id':'test','name':'Test API','kind':'demo','enabled':True,'url':'https://example.invalid/quality','token_env':'QC_TEST_TOKEN'}]}));monkeypatch.setattr(conn,'CONFIG',config)
    monkeypatch.setenv('QC_TEST_TOKEN','private-test-secret')
    client=httpx.Client
    def handle(request):
        assert request.headers['Authorization']=='Bearer private-test-secret'
        return httpx.Response(200,json=[x.model_dump() for x in records()])
    monkeypatch.setattr(httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(handle),**kw))
    assert conn.sync('test')['records']==8
    assert 'private-test-secret' not in json.dumps(conn.catalog())
    with pytest.raises(ValueError):conn.sync('absent')
def test_api_routes(database):
    with TestClient(create_app(Store())) as c:
        r=c.post('/api/qc/import',json={'name':'API','kind':'demo','records':[x.model_dump() for x in records()]});assert r.status_code==200
        identifier=r.json()['id'];analysis=c.get('/api/qc/signals',params={'dataset_id':identifier}).json();signal=analysis['signals'][0]
        assert c.post('/api/qc/review',json={'dataset_id':identifier,'signal_id':signal['id'],'actor':'Tester','action':'approve','note':'Reviewed'}).status_code==200
        assert c.post('/api/qc/review',json={'dataset_id':identifier,'signal_id':'fake','actor':'Tester','action':'approve','note':'Reviewed'}).status_code==400
        assert 'study,site,month' in c.get('/api/qc/export',params={'dataset_id':identifier}).text
        assert len(c.get('/api/qc/audit',params={'dataset_id':identifier}).json())==2
        assert c.get('/api/qc/signals',params={'dataset_id':'missing'}).status_code==400

def test_knowledge_quotes_retain_locator(tmp_path,monkeypatch):
    from backend.database.postgres import connection
    with connection('knowledge') as c:
        c.execute('INSERT INTO sources VALUES (%s,%s)',('a',json.dumps({'id':'a','title':'Reference'})))
        c.execute('INSERT INTO chunks VALUES (%s,%s,%s)',('a','page 9','Human review and CAPA'))
    r=kb.search('CAPA " OR ***');assert r[0]['locator']=='page 9' and r[0]['text']=='Human review and CAPA'
    assert kb.search('')==[]

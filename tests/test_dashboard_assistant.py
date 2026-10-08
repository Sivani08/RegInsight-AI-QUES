import copy
import pytest
from pydantic import ValidationError
from pg_client import TestClient
from backend.api.main import create_app
from backend.database.store import Store
from backend.database.load import load
from backend.analytics.metrics import metrics
from backend.analytics.dashboard_queries import aggregate
from backend.semantic.models import QueryRequest,QueryPlan,Filters
from backend.semantic.planner import plan
from backend.semantic.resolver import resolve
from backend.semantic.catalog import FOCUSES
from backend.services.dashboard_insights import DashboardInsights,validate_numeric
from backend.services.intelligence import Intelligence

@pytest.fixture
def store():
    s=Store();load(store=s);return s
@pytest.fixture
def client(store):
    with TestClient(create_app(store)) as c:yield c
def ask(client,q,**kwargs):
    response=client.post('/api/agent/dashboard-query',json={'question':q,**kwargs})
    assert response.status_code==200,response.text
    return response.json()

@pytest.mark.parametrize('text,metric',[('inspection volume','total_inspections'),('official action rate','oai_rate'),('highest risk sites','high_risk_sites'),('repeated themes','recurring_themes'),('Has OAI increased?','oai_count')])
def test_aliases(text,metric):assert metric in resolve(text)
def test_longest_alias():assert resolve('official action rate')==['oai_rate']
@pytest.mark.parametrize('change',[{'metrics':['invented']},{'dimensions':['password']},{'filters':{'sql':'x'}},{'limit':51},{'filters':{'start_year':2026,'end_year':2025}},{'filters':{'start_date':'2026-02-01','end_date':'2026-01-01'}},{'metrics':['severity_distribution'],'focus':'inspection_activity'}])
def test_plan_rejects(change):
    with pytest.raises(ValidationError):QueryPlan(**({'intent':'summary','focus':'inspection_activity','metrics':['total_inspections'],'dimensions':['year']}|change))
def test_valid_plan():
    q=QueryPlan(intent='trend_analysis',focus='citation_oai_trend',metrics=['oai_rate'],dimensions=['year'],filters=Filters(year=2025))
    assert q.filters.year==2025
@pytest.mark.parametrize('filters',[{}, {'year':2025},{'classification':'OAI'},{'company':'Aster Therapeutics'},{'company':'No matches'}])
def test_sql_parity(store,filters):
    old=metrics(store.search(lightweight=True,**filters),store.info()['as_of'])
    new=aggregate(store,store.info()['as_of'],filters)
    for k,v in old.items():assert new[k]==v,(k,new[k],v)
@pytest.mark.parametrize('filters',[{}, {'year':2025},{'classification':'OAI'},{'company':'Aster Therapeutics'}])
def test_dashboard_consistency(client,filters):
    d=client.get('/api/dashboard',params=filters).json()
    a=ask(client,'What stands out in this dashboard?',filters=filters)
    for k,v in d['metrics'].items():assert a['layers']['metrics'][k]==v
    assert a['layers']['metrics']['risk_distribution']==d['risk_distribution']
    assert len(a['layers']['evidence_and_limitations']['records'])<=10
def test_followups_and_evidence(client):
    first=ask(client,'Which sites have the highest risk?',limit=5)
    key=first['supporting_data'][0]['key'];risk=first['supporting_data'][0]['risk']
    why=ask(client,'Why is the first one high?',context=first['context'])
    assert why['semantic_plan']['filters']['site']==key
    assert why['layers']['metrics']['risk_score']==risk['score']
    assert why['layers']['metrics']['risk_components']==risk['components']
    detail=ask(client,'Show the inspections.',context=why['context'])
    assert detail['semantic_plan']['filters']['site']==key
    evidence=ask(client,'What evidence supports that?',context=why['context'])
    assert evidence['layers']['metrics']['risk_score']==risk['score']
    how=ask(client,'How did you calculate that?',context=why['context'])
    assert how['layers']['evidence_and_limitations']['definitions']['risk_score']
    assert client.get('/api/evidence/'+how['evidence_id']).json()['records']
def test_filter_change_clears_context(client):
    a=ask(client,'Which sites have the highest risk?')
    b=ask(client,'What stands out?',context=a['context'],filters={'year':2025})
    assert {k:v for k,v in b['semantic_plan']['filters'].items() if v is not None}=={'year':2025}
def test_previous_year(client):
    a=ask(client,'What changed from last year?',focus='citation_oai_trend')
    assert a['semantic_plan']['comparison']=='previous_period'
    assert a['semantic_plan']['dimensions']==['year']
    assert a['layers']['patterns']['latest_year']>a['layers']['patterns']['previous_year']
def test_pagination(client):
    a=ask(client,'Which sites are highest risk?',limit=2)
    b=ask(client,'Which sites are highest risk?',limit=2,offset=2)
    assert len(a['supporting_data'])==2
    assert not set(r['key'] for r in a['supporting_data'])&set(r['key'] for r in b['supporting_data'])
@pytest.mark.parametrize('body',[{'question':'a'*4001},{'question':'x','history':[{'role':'user','content':'x'}]*13},{'question':'x','limit':51},{'question':'x','filters':{'sql':'SELECT'}},{'question':'   '}])
def test_input_limits(client,body):assert client.post('/api/agent/dashboard-query',json=body).status_code==422
def test_sql_rejected(client):assert client.post('/api/agent/dashboard-query',json={'question':'select * from inspections'}).status_code==400
def test_numeric_boundary(store):
    r=DashboardInsights(Intelligence(store)).query(QueryRequest(question='What stands out?'))
    authority=copy.deepcopy(r.layers.metrics)
    r.insights[0].metrics['total_inspections']=999999
    with pytest.raises(ValueError):validate_numeric(r,authority,r.layers.patterns)
def test_inspection_focuses(client):
    for focus in FOCUSES:
        if focus not in ('observation_intelligence','recurring_risk_signals'):
            a=ask(client,'What stands out in this graph?',focus=focus)
            assert a['semantic_plan']['focus']==focus
            assert 2<=len(a['suggested_questions'])<=4
def test_bounded_rank_sql(store):
    from sqlalchemy import event
    sql=[]
    event.listen(store.engine,'before_cursor_execute',lambda conn,cursor,statement,parameters,context,executemany:sql.append(statement))
    DashboardInsights(Intelligence(store)).query(QueryRequest(question='Which sites have the highest risk?',limit=3))
    assert any('ORDER BY' in s and 'LIMIT' in s and 'dashboard_scope_sites.payload' in s for s in sql)

def test_security_headers(client):
    r=client.get('/api/health');assert r.headers['x-content-type-options']=='nosniff'
    assert "frame-ancestors 'none'" in r.headers['content-security-policy']
def test_csrf(client):assert client.post('/api/auth/logout',json={},headers={'Origin':'https://attacker.example'}).status_code==403
def test_access_key_and_revocation(monkeypatch,store):
    from fastapi.testclient import TestClient as RawClient
    from backend.database.postgres import connection
    from backend.api.identity import digest
    import uuid
    with connection() as current:
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',(str(uuid.uuid4()),'Session test','analyst',digest('test-key-32-characters-minimum-secret')))
    with RawClient(create_app(store)) as c:
        assert c.get('/api/dashboard').status_code==401
        assert c.post('/api/auth/login',json={'access_key':'bad'}).status_code==401
        r=c.post('/api/auth/login',json={'access_key':'test-key-32-characters-minimum-secret'})
        assert r.status_code==200 and 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
        token=c.cookies.get('reginsight_session');assert c.get('/api/dashboard').status_code==200
        c.post('/api/auth/logout');c.cookies.set('reginsight_session',token)
        assert c.get('/api/dashboard').status_code==401
def test_production_fails_closed(monkeypatch,store):
    monkeypatch.setenv('REGINSIGHT_ENV','production');monkeypatch.delenv('REGINSIGHT_ACCESS_KEY',raising=False)
    from fastapi.testclient import TestClient as RawClient
    with RawClient(create_app(store)) as c:
        assert c.get('/api/dashboard').status_code==401

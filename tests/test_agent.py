
import pytest
from backend.agents.investigator import InspectionAgent
from backend.services.intelligence import Intelligence
from backend.database.store import Store
from backend.database.load import load
from backend.tools.registry import Tools
from pg_client import TestClient
from backend.api.main import create_app

@pytest.fixture
def service():
    store=Store();load(store=store);return Intelligence(store)

def test_acceptance_and_evidence(service):
    agent=InspectionAgent(service);r=agent.query('Why is Aster Therapeutics considered high risk?')
    result=r['results'][0]
    assert result['risk']==service.risk(company='Aster Therapeutics')
    assert {x['tool'] for x in r['tools']}==set(Tools(service).registry)
    evidence=service.store.get_evidence(r['analysis_id'])
    assert {t['tool'] for t in evidence['tools']}==set(Tools(service).registry)
    assert len(evidence['records'])==result['risk']['metrics']['total_inspections']
    assert sum(x['classification']=='OAI' for x in evidence['records'])==result['risk']['metrics']['OAI']
    assert all(i in {r['inspection_id'] for r in evidence['records']} for theme in result['recurring_issues'] for i in theme['inspection_ids'])
    with TestClient(create_app(service.store)) as c:
        assert c.post('/api/agent/query',json={'question':'Why is Aster high risk?'}).status_code==200
        e=c.get('/api/evidence/'+r['analysis_id'],params={'limit':2}).json()
        assert len(e['records'])==2 and e['record_count']==r['evidence_count']

def test_comparison_ranking_and_unknown(service):
    a=InspectionAgent(service)
    assert len(a.query('Compare Aster Therapeutics and Northstar Biologics')['results'])==2
    ranked=a.query('Which sites should management investigate first?')['results']
    assert len(ranked)==5
    assert [r['risk']['score'] for r in ranked]==sorted([r['risk']['score'] for r in ranked],reverse=True)
    with pytest.raises(ValueError): a.query('Why is Imaginary Corp high risk?')
    with pytest.raises(ValueError): a.query('Compare Aster')
    with pytest.raises(ValueError): Tools(service).call('delete_everything')
    with pytest.raises(ValueError): Tools(service).call('search_inspections',sql='SELECT *')

def test_theme_change_and_context(service):
    a=InspectionAgent(service)
    r=a.query('Which risk themes increased over the last three years?')
    assert len(r['theme_changes'])==12
    contextual=a.query('Why is this site high risk?',site='SYN-FEI-0011')
    assert contextual['results'][0]['scope']['site']=='SYN-FEI-0011'
    assert contextual['results'][0]['risk']==service.risk(site='SYN-FEI-0011')

def test_explicit_entities_override_context(service):
    a=InspectionAgent(service)
    r=a.query('Compare Aster Therapeutics and Northstar Biologics',company='Aster Therapeutics',site='SYN-FEI-0011')
    assert len(r['results'])==2
    assert all('company' in r['scope'] for r in r['results'])

import json
import os
import pytest
from fastapi.testclient import TestClient
from backend.api.main import create_app
from backend.database.store import Store
from backend.services.intelligence import Intelligence
from backend.agents.investigator import InspectionAgent

TEST_DATABASE_URL = os.getenv('REGINSIGHT_TEST_DATABASE_URL')

@pytest.mark.skipif(not TEST_DATABASE_URL, reason='Set REGINSIGHT_TEST_DATABASE_URL to a PostgreSQL test database')
def test_real_dataset_reconciliation_and_benchmarks():
    store=Store(TEST_DATABASE_URL, allow_fallback=False)
    assert store.dialect == 'postgresql'
    s=Intelligence(store);q=s.info();d=s.dashboard()
    assert q['valid_records']==274886
    assert q['total_records']==q['valid_records']+q['merged_project_rows']
    assert sum(d['risk_distribution'].values())==133375
    assert d['metrics']['citation_rate'] is None and d['metrics']['average_observations'] is None
    assert d['metrics']['available_citation_rows']==280130
    with TestClient(create_app(store)) as c:
        b=c.get('/api/benchmarks').json()
        assert [y['frequency_sum'] for y in b['trend']]==[13012,13009,15265]
        assert [y['forms_483_in_system'] for y in b['system_totals']]==[4428,4056,4862]
        result=c.get('/api/inspections',params={'limit':2}).json()
        assert result['total']==274886 and len(result['records'])==2
        companies=c.get('/api/companies',params={'search':'lupin'}).json()
        assert companies
    company=companies[0]['company_name']
    result=InspectionAgent(s).query('Why is this company considered high risk?',company=company)
    risk=result['results'][0]['risk']
    assert risk==s.risk(company=company)
    assert 'citation_history' in risk['missing_factors'] and 'severity' in risk['missing_factors']
    evidence=store.get_evidence(result['analysis_id'])
    assert all('inspection_rows' in json.loads(r['source_record']) for r in evidence['records'])
    assert all(r['company_name'].casefold()==company.casefold() for r in evidence['records'])

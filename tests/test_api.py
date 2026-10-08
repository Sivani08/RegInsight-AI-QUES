import pytest
from pg_client import TestClient
from backend.api.main import create_app
from backend.database.store import Store
from backend.database.load import load

@pytest.fixture
def client():
    store=Store()
    load(store=store)
    with TestClient(create_app(store)) as c: yield c

def test_dashboard_consistency(client):
    d=client.get('/api/dashboard').json()
    q=client.get('/api/data-quality').json()
    assert d['metrics']['total_inspections']==q['valid_records']==211
    assert sum(d['metrics'][k] for k in ['OAI','VAI','NAI','Unknown'])==211
    assert sum(d['risk_distribution'].values())==len(d['sites'])

def test_profile_and_filters(client):
    rows=client.get('/api/inspections',params={'company':'Aster Therapeutics','limit':2}).json()
    assert len(rows['records'])==2 and rows['total']>2
    profile=client.get('/api/profile',params={'company':'Aster Therapeutics'}).json()
    assert profile['risk']['metrics']['total_inspections']==rows['total']
    for path in ['/api/risk','/api/trends','/api/recurrence','/api/sites','/api/companies']:
        assert client.get(path).status_code==200
    assert client.get('/api/inspections',params={'limit':0}).status_code==422
    assert client.get('/api/trends',params={'start_year':2026,'end_year':2020}).status_code==400
    assert client.get('/api/evidence/missing').status_code==404
    assert client.get('/api/profile',params={'company':'Unknown company'}).status_code==400

def test_missing_dataset():
    with TestClient(create_app(Store())) as c:
        assert c.get('/api/health').json()['dataset_loaded'] is False
        assert c.get('/api/dashboard').status_code==400

"""Website search, evidence scope and review integrity, using isolated source data."""
import json
import pytest
from pg_client import TestClient
from backend.api.main import create_app
from backend.api import workspace
from backend.database.store import Store
from backend.services import observation_intelligence as intelligence
from data_engineering.intelligence_sources import db, add


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = 'intelligence'
    monkeypatch.setenv('REDIS_ENABLED', 'false')
    monkeypatch.setattr(workspace, 'DB', path)
    stats = dict(source_observation_rows=0, duplicate_observation_rows=0, empty_text_rows=0, conflicting_records=0)
    with db(path) as c:
        for i, name in enumerate(['Alpha facility','Beta facility','Gamma facility']):
            add(c, dict(dataset='real',grain='inspection',inspection_id=str(i),
                text='Original laboratory records were not retained after testing.',
                metadata=dict(company=name,site='SITE-'+str(i),year=2023+i),
                source=dict(file='source.csv',row=str(i+2))), stats)
        add(c, dict(dataset='annual',grain='annual_template',inspection_id=None,
            text='Original laboratory records were not retained after testing.',frequency=50,
            metadata=dict(year=2025),source=dict(file='annual.xlsx',row='2')),stats)
        c.execute('INSERT INTO corpus VALUES (%s,%s)',('quality',json.dumps(stats)))
    intelligence.run(path=path,provider='rules')
    with TestClient(create_app(Store())) as test_client:
        yield test_client


def test_scope_sort_search_and_pagination(client):
    summary = client.get('/api/workspace/summary?dataset=real').json()
    assert summary['stats']['observations'] == 3
    assert summary['stats']['inspections'] == 3
    assert summary['stats']['recurring_themes'] == 1
    assert sum(r['count'] for r in summary['severity']) == 3
    first = client.get('/api/workspace/observations?sort=facility&direction=asc&limit=1').json()
    second = client.get('/api/workspace/observations?sort=facility&direction=asc&limit=1&offset=1').json()
    assert first['records'][0]['company'] == 'Alpha facility'
    assert second['records'][0]['company'] == 'Beta facility'
    found = client.get('/api/workspace/observations?search=gamma').json()
    assert found['total'] == 1 and found['records'][0]['fiscal_year'] == 2025
    assert client.get('/api/workspace/observations?search=%25').json()['total'] == 0
    assert client.get('/api/workspace/observations?sort=DROP%20TABLE').status_code == 422
    assert client.get('/api/workspace/observations?limit=0').status_code == 422
    assert client.get('/api/workspace/observations?run_id=missing').status_code == 400
    assert client.get('/api/workspace/observations?search=laboratory').json()['total'] == 3

def test_indexed_search_matches_scan(client):
    from backend.services.retrieval_search import prepare_text_search,prepare_metadata_search
    from backend.cache.redis_cache import get_cache
    queries=['laboratory','ALPHA','SITE-1','%25','"a"','zzzz','ab','é']
    before={q:client.get('/api/workspace/observations',params={'search':q}).json() for q in queries}
    with db(workspace.DB) as c:
        prepare_text_search(c);prepare_metadata_search(c)
    get_cache.cache_clear()
    for q in queries:
        assert client.get('/api/workspace/observations',params={'search':q}).json()==before[q]


def test_reviews_are_append_only_with_conflict_detection(client):
    page = client.get('/api/workspace/observations').json()
    record = page['records'][0]
    body = dict(run_id=page['run_id'],observation_id=record['observation_id'],revision=0,
        action='Approve',reviewer='Test reviewer',note='Compared the source quote and classification.')
    saved = client.post('/api/workspace/reviews',json=body)
    assert saved.status_code == 201
    assert saved.json()['revision'] == 1
    assert saved.json()['original_classification'] == record['tag']
    assert client.post('/api/workspace/reviews',json=body).status_code == 409
    invalid = {**body,'revision':1,'action':'Modify','theme':'Invented','severity':'High'}
    assert client.post('/api/workspace/reviews',json=invalid).status_code == 422
    changed = {**body,'revision':1,'action':'Modify','theme':'Data Integrity','severity':'Medium'}
    assert client.post('/api/workspace/reviews',json=changed).status_code == 201
    rejected = {**body,'revision':2,'action':'Reject','note':'Further evidence is needed.'}
    assert client.post('/api/workspace/reviews',json=rejected).status_code == 201
    history = client.get('/api/workspace/reviews',params={k:body[k] for k in ['run_id','observation_id']}).json()
    assert [r['revision'] for r in history] == [3,2,1]
    refreshed = client.get('/api/workspace/observations').json()['records'][0]
    assert refreshed['tag'] == record['tag']
    assert refreshed['review']['action'] == 'Reject'
    assert client.post('/api/workspace/reviews',json={**body,'reviewer':'   '}).status_code == 422
    assert client.post('/api/workspace/reviews',json={**body,'observation_id':'missing'}).status_code == 404


def test_access_log_format_is_preserved_and_redacted(monkeypatch):
    import logging
    from uvicorn.logging import AccessFormatter
    from backend.genai.redaction import install_redaction
    monkeypatch.setenv('AI_API_KEY','test-secret-value')
    install_redaction()
    record = logging.getLogRecordFactory()('uvicorn.access', logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ('127.0.0.1','GET','/path?value=test-secret-value','1.1',200), None)
    output = AccessFormatter('%(message)s', use_colors=False).format(record)
    assert 'test-secret-value' not in output
    assert '[REDACTED]' in output

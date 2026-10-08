import json
import pytest
from pg_client import TestClient
from backend.api.main import create_app
from backend.api import workspace
from backend.database.store import Store
from backend.database.load import load
from backend.services import observation_intelligence as intelligence
from data_engineering.intelligence_sources import db,add

@pytest.fixture
def client(tmp_path,monkeypatch):
    path='intelligence';monkeypatch.setattr(workspace,'DB',path)
    stats=dict(source_observation_rows=0,duplicate_observation_rows=0,empty_text_rows=0,conflicting_records=0)
    with db(path) as c:
        for i in range(4):
            add(c,dict(dataset='real',grain='inspection',inspection_id=str(i),text='Original laboratory records were not retained after testing.',metadata=dict(company='Aster Therapeutics',site='SITE-1',year=2023+i%2),source=dict(file='source.csv',row=str(i+2))),stats)
        c.execute('INSERT INTO corpus VALUES (%s,%s)',('quality',json.dumps(stats)))
    intelligence.run(path=path,provider='rules')
    store=Store();load(store=store)
    with TestClient(create_app(store)) as c:yield c

def query(c,q,**kwargs):
    r=c.post('/api/agent/dashboard-query',json={'question':q,**kwargs});assert r.status_code==200,r.text;return r.json()
def test_observation_counts_and_scope(client):
    r=query(client,'What stands out in this graph?',focus='observation_intelligence')
    assert r['layers']['metrics']['observation_count']==4
    assert sum(x['count'] for x in r['layers']['metrics']['severity_distribution'])==4
    assert r['supporting_data'][0]['source_file']=='source.csv'
    s=client.get('/api/workspace/summary?dataset=real').json()
    assert r['layers']['metrics']['observation_count']==s['stats']['observations']
    f=query(client,'What stands out?',focus='observation_intelligence',filters={'year':2023})
    assert f['layers']['metrics']['observation_count']==2
def test_recurring_theme_context(client):
    r=query(client,'What themes recur most?')
    assert r['layers']['metrics']['recurring_themes']==1
    assert r['layers']['metrics']['recurrence_count']==3
    more=query(client,'Which sites repeatedly show this theme?',context=r['context'])
    assert more['semantic_plan']['filters']['theme']
    assert more['supporting_data'][0]['site']=='SITE-1'
def test_observation_similar_context(client):
    r=query(client,'Which observations require review?')
    assert r['layers']['metrics']['review_required_count']==4
    assert 'observation_id' in r['supporting_data'][0]
    similar=query(client,'Show similar observations.',context=r['context'])
    assert similar['semantic_plan']['filters']['semantic_group']
    assert similar['layers']['metrics']['observation_count']==4
def test_invalid_cross_dataset_filter(client):
    r=client.post('/api/agent/dashboard-query',json={'question':'What stands out?','focus':'observation_intelligence','filters':{'classification':'OAI'}})
    assert r.status_code==400

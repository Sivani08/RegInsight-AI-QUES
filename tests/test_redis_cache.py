import json
import pytest
import fakeredis
from backend.cache.redis_cache import RedisCache
from backend.cache import snapshots
from backend.services import observation_intelligence as service
from data_engineering.intelligence_sources import db,add
TEXT='Original laboratory records were not retained after testing.'
@pytest.fixture
def cache(monkeypatch):
    c=RedisCache(fakeredis.FakeRedis(decode_responses=True),enabled=True)
    monkeypatch.setattr(snapshots,'get_cache',lambda:c)
    monkeypatch.setattr(service,'get_cache',lambda:c)
    return c
@pytest.fixture
def corpus(tmp_path):
    path='intelligence';stats={'source_observation_rows':0,'duplicate_observation_rows':0,'empty_text_rows':0,'conflicting_records':0}
    with db(path) as c:
        for i in range(3):
            add(c,{'dataset':'real','grain':'inspection','inspection_id':str(i),'text':TEXT,'metadata':{'company':'Test Company','site':'S'+str(i),'year':2023+i},'source':{'file':'fixture.csv','row':str(i)}},stats)
        c.execute('INSERT INTO corpus VALUES (%s,%s)',('quality',json.dumps(stats)))
    service.run(path=path)
    return path

def test_snapshot_hit_avoids_query_and_preserves_types(cache,corpus,monkeypatch):
    first=service.tags(path=corpus,limit=1)
    def blocked(*a,**kw):raise AssertionError('SQL query should not execute on a hit')
    monkeypatch.setattr(service,'scope',blocked)
    second=service.tags(path=corpus,limit=1)
    assert first==second and cache.stats['hits']>=1
    second.records.clear()
    assert len(service.tags(path=corpus,limit=1).records)==1

def test_filter_page_and_new_run_isolation(cache,corpus):
    a=service.tags(path=corpus,limit=1);b=service.tags(path=corpus,limit=1,offset=1)
    assert a.records[0].observation_id!=b.records[0].observation_id
    assert service.tags(path=corpus,company='Absent').total==0
    service.run(path=corpus)
    assert service.tags(path=corpus,limit=1).run_id!=a.run_id

def test_metrics_and_similar_are_cached(cache,corpus,monkeypatch):
    m=service.metrics(path=corpus)
    page=service.tags(path=corpus);oid=page.records[0].observation_id
    related=service.similar(oid,path=corpus)
    monkeypatch.setattr(service,'scope',lambda **kw:pytest.fail('uncached query'))
    assert service.metrics(path=corpus)==m
    assert service.similar(oid,path=corpus)==related

def test_corrupt_value_recomputes(cache,corpus):
    first=service.tags(path=corpus)
    keys=list(cache.client.scan_iter(match='*:tags:*'));assert len(keys)==1
    cache.client.set(keys[0],'{bad json')
    assert service.tags(path=corpus)==first
    cache.client.set(keys[0],json.dumps({'run_id':'wrong','total':0,'records':[]}))
    assert service.tags(path=corpus)==first
    assert cache.stats['invalid']==2

def test_redis_outage_falls_back_and_circuit_recovers(cache,corpus):
    class Down:
        def get(self,*a):raise ConnectionError('redis://password-secret@server')
    cache.client=Down()
    assert service.tags(path=corpus).total==3
    assert cache.stats['errors']==1
    assert service.tags(path=corpus).total==3 and cache.stats['errors']==1
    cache.client=fakeredis.FakeRedis(decode_responses=True);cache.retry_at=0
    assert service.tags(path=corpus).total==3 and cache.stats['writes']>0

def test_disabled_ttl_size_and_secret_safe_status():
    fake=fakeredis.FakeRedis(decode_responses=True);c=RedisCache(fake,enabled=False)
    c.put('x',{'v':1});assert fake.get('x') is None
    c.enabled=True;c.put('x',{'v':1},ttl=10);assert 0<fake.ttl('x')<=10
    assert c.get('x')=={'v':1};fake.expireat('x',1);assert c.get('x') is None
    c.max_bytes=2;c.put('big',{'large':'payload'});assert fake.get('big') is None
    assert 'redis://' not in json.dumps(c.status())

def test_classification_recovers_durable_cache_from_redis(cache,corpus):
    # Redis must never become the only copy required for evidence joins.
    with db(corpus) as c:c.execute('DELETE FROM cache')
    result=service.run(path=corpus)
    assert result['redis_classification_hits']==1 and result['api_requests']==0
    assert service.tags(path=corpus).total==3

def test_evidence_corruption_rejected(cache,corpus):
    first=service.tags(path=corpus)
    key=next(cache.client.scan_iter(match='*:tags:*'))
    raw=first.model_dump();raw['records'][0]['tag']['evidence_quote']='fabricated'
    cache.client.set(key,json.dumps(raw))
    assert service.tags(path=corpus)==first
    assert cache.stats['invalid']==1

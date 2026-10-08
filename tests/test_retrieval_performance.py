import threading,time
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.cache.redis_cache import RedisCache
from backend.database.store import Store,inspections
from backend.database.load import load
from backend.database.retrieval_mart import prepare,table_for,facts
from backend.analytics.dashboard_queries import aggregate
from backend.services.retrieval_search import prepare_text_search,text_predicate

def test_cache_single_flight_copies_and_expiry():
    now=[0];cache=RedisCache(enabled=False,clock=lambda:now[0]);calls=[];ready=threading.Event()
    def factory():calls.append(1);ready.wait(2);return {'rows':[1]}
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs=[pool.submit(cache.remember,'same',factory,10) for _ in range(5)]
        time.sleep(.03);ready.set();values=[j.result() for j in jobs]
    assert len(calls)==1
    values[0]['rows'].append(2)
    assert cache.remember('same',factory,10)=={'rows':[1]}
    now[0]=11;cache.remember('same',factory,10);assert len(calls)==2

def test_cache_failures_and_bounded_entries():
    cache=RedisCache(enabled=False);cache.local_entries=2
    def fail():raise ValueError('failed query')
    with pytest.raises(ValueError):cache.remember('bad',fail)
    assert not cache.pending and not cache.local
    for i in range(8):assert cache.remember(str(i),lambda:i)==i
    assert len(cache.local)==2 and cache.local_bytes<=cache.local_limit

def test_projection_parity_and_replacement(tmp_path):
    store=Store();load(store=store)
    filters=[{}, {'year':2025},{'classification':'OAI'},{'company':'Aster Therapeutics'},{'company':'missing'}]
    original=[aggregate(store,store.info()['as_of'],f) for f in filters]
    evidence=store.search(limit=1);prepare(store)
    assert table_for(store) is facts
    assert [aggregate(store,store.info()['as_of'],f) for f in filters]==original
    assert store.search(limit=1)==evidence
    info=store.info();info['valid_records']=1;store.replace(evidence,info)
    assert table_for(store) is inspections
    prepare(store);assert table_for(store) is facts
    assert aggregate(store,store.info()['as_of'],{'classification':evidence[0]['classification']})['total_inspections']==1

@pytest.mark.parametrize('query',['laboratory','LAB','100%','_','"a"','bé','retained','zzzz','ab'])
def test_trigram_matches_original_literal(query):
    from backend.database.postgres import connection
    with connection('intelligence') as c:
        values=['Laboratory records were retained','100% complete','contains _ and "a"','bé abc','zz']
        c.cursor().executemany('INSERT INTO texts VALUES (%s,%s)',[(str(i),v) for i,v in enumerate(values)])
        prepare_text_search(c)
        c.execute("INSERT INTO texts VALUES ('new','New LAB records')")
        sql,args=text_predicate(c,query)
        actual={row[0] for row in c.execute(sql,args)}
        expected={row[0] for row in c.execute('SELECT hash FROM texts WHERE strpos(lower(text),lower(%s))>0',(query,))}
        assert actual==expected

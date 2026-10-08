import pytest
from backend.analytics.graph_insights import graph_insights

def test_partial_year_is_not_presented_as_a_full_year_decline():
    rows=[{'year':2024,'total_inspections':100,'oai_rate':.10}, {'year':2025,'total_inspections':120,'oai_rate':.12}, {'year':2026,'total_inspections':30,'oai_rate':.2,'partial_year':True}]
    metrics={'total_inspections':250,'NAI':200,'VAI':30,'OAI':20,'Unknown':0,'citation_known':0}
    result=graph_insights(metrics,rows,{'HIGH':3,'CRITICAL':1,'LOW':6},'2026-09-10')
    activity=result['inspection_activity']
    assert '30 inspections' in activity['headline'] and 'so far' in activity['headline']
    assert '2026 is partial' in activity['detail']
    assert '2025 has 20 more inspections than 2024' in activity['detail']
    assert '90 fewer' not in activity['detail']
    assert '20.00%' in result['citation_oai_trend']['headline']
    assert 'unavailable' in result['citation_oai_trend']['detail']
    assert '80.0%' in result['classification_distribution']['headline']
    assert 'out of 10 sites' in result['risk_distribution']['headline']

def test_no_matches_does_not_invent_rates():
    for item in graph_insights({'total_inspections':0},[]).values():
        assert 'No inspections match' in item['headline']
        assert '0%' not in item['headline']

def test_missing_dates_and_tied_classifications():
    r=graph_insights({'total_inspections':10,'NAI':5,'VAI':5,'OAI':0,'oai_rate':0,'citation_rate':None},[])
    assert 'No dated' in r['inspection_activity']['headline']
    assert 'tied' in r['classification_distribution']['headline']
    assert '0.00%' in r['citation_oai_trend']['headline']

def test_single_period_and_citation_gaps():
    r=graph_insights({'total_inspections':10,'NAI':10},[{'year':2025,'total_inspections':10,'oai_rate':None,'citation_rate':.2}])
    assert 'OAI rate is unavailable' in r['citation_oai_trend']['headline']
    assert 'missing values are not zeros' in r['citation_oai_trend']['detail']

def test_dashboard_and_copilot_share_chart_headlines():
    from pg_client import TestClient
    from backend.database.store import Store
    from backend.database.load import load
    from backend.api.main import create_app
    store=Store();load(store=store)
    with TestClient(create_app(store)) as c:
        for filters in ({},{'year':2025},{'classification':'OAI'},{'company':'No matches'}):
            d=c.get('/api/dashboard',params=filters).json()
            for focus,summary in d['graph_insights'].items():
                r=c.post('/api/agent/dashboard-query',json={'question':'What stands out in this graph?','focus':focus,'filters':filters})
                assert r.status_code==200,r.text
                assert r.json()['headline']==summary['headline']

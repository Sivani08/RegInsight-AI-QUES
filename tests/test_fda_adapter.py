import json
from data_engineering.fda_source_adapter import canonicalize
from backend.analytics.metrics import metrics
def test_project_grain_and_missing_counts():
    base={'id':'1','fei':'123','date':'2025-01-01','company':'Example','city':'City','state':'State','country':'USA','fy':2025,'product':'Drugs','raw':'{}','posted':'No'}
    rows=[dict(base,source_row=2,classification='No Action Indicated (NAI)',project='A'),dict(base,source_row=3,classification='Official Action Indicated (OAI)',project='B')]
    r=canonicalize(rows,[],'2026-09-10')
    assert r['classification']=='OAI' and len(r['project_classifications'])==2
    assert r['observation_count'] is None and r['citation_indicator'] is None
    assert r['available_citation_count']==0 and r['posted_citation_indicator']==0
    m=metrics([r],'2026-09-10')
    assert m['citation_positive'] is None and m['citation_rate'] is None
    assert len(json.loads(r['source_record'])['inspection_rows'])==2

def test_citation_identity_validation():
    import pytest
    row={'id':'1','fei':'123','date':'2025-01-01','company':'Example','city':'City','state':'State','country':'USA','fy':2025,'product':'Drugs','raw':'{}','posted':'Yes','source_row':2,'classification':'Voluntary Action Indicated (VAI)','project':'A'}
    with pytest.raises(ValueError,match='identity mismatch'):canonicalize([row],[{'id':'2','fei':'123','date':'2025-01-01'}],'2026-09-10')

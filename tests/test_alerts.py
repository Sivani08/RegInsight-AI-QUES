from backend.analytics.alerts import site_alerts
from backend.risk.engine import load_config

def test_all_alerts_grounded():
    records=[]
    for year in [2025,2026]:
        for i in range(3):
            records.append({'inspection_id':f'{year}-{i}','site_key':'x','inspection_date':f'{year}-01-01','inspection_year':year,
                'classification':'OAI' if year==2026 else 'NAI','citation_indicator':int(year==2026),
                'observation_count':5,'observation_text':'Repeated CAPA failed. Audit trail disabled; records were deleted.'})
    result=site_alerts(records,'2026-09-10',load_config())
    assert {r['code'] for r in result}=={'HIGH_RISK_SITE','REPEATED_OAI','CITATION_RATE_INCREASE','RECURRING_DATA_INTEGRITY','NEW_HIGH_SEVERITY_SIGNAL'}
    assert all(set(r['inspection_ids'])<=set(x['inspection_id'] for x in records) for r in result)
    assert site_alerts([],'2026-09-10',load_config())==[]

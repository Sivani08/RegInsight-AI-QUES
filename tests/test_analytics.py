from copy import deepcopy
from backend.risk.engine import calculate_risk, load_config
from backend.analytics.metrics import metrics,analyze_trend,find_recurring_risks

def rows():
    return [{'inspection_id':str(i),'inspection_year':2023+i,'inspection_date':f'{2023+i}-01-01',
             'classification':'NAI' if i==0 else 'OAI','citation_indicator':0 if i==0 else 1,
             'observation_count':0 if i==0 else 5,'observation_text':'' if i==0 else 'CAPA audit trail failed.'} for i in range(3)]

def test_deterministic_and_boundaries():
    a=calculate_risk(rows(),'2026-09-10'); b=calculate_risk(list(reversed(rows())),'2026-09-10')
    assert a==b and 0<=a['score']<=100
    assert abs(sum(c['points'] or 0 for c in a['components'])-a['score'])<0.03
    cfg=load_config(); cfg['weights']={k:0 for k in cfg['weights']}; cfg['weights']['citation_history']=100
    for rate,expected in [(0,'LOW'),(.3,'MODERATE'),(.6,'HIGH'),(.8,'CRITICAL')]:
        r=[dict(rows()[0],inspection_id=str(i),citation_indicator=int(i<rate*10)) for i in range(10)]
        assert calculate_risk(r,'2026-09-10',cfg)['band']==expected

def test_known_denominators_and_empty():
    r=rows()+[{'inspection_id':'unknown'}]
    m=metrics(r,'2026-09-10')
    assert m['total_inspections']==4 and m['citation_known']==3 and m['citation_rate']==0.666667
    assert calculate_risk([{'inspection_id':'unknown'}],'2026-09-10')['score'] is None
    assert calculate_risk([],'2026-09-10')['band']=='INSUFFICIENT DATA'

def test_trend_no_future_leakage():
    c=load_config(); r=rows()
    trend=analyze_trend(r,'2026-09-10',c)
    assert trend[0]['citation_rate']==0 and trend[-1]['citation_rate']==1
    changed=deepcopy(r); changed[-1]['observation_count']=100
    assert analyze_trend(changed,'2026-09-10',c)[0]==trend[0]

def test_recurrence_counts_inspections():
    r=rows(); r[-1]['observation_text']='CAPA CAPA CAPA audit trail'
    result={v['theme']:v for v in find_recurring_risks(r)}
    assert result['CAPA']['count']==2 and result['CAPA']['repeat_count']==1

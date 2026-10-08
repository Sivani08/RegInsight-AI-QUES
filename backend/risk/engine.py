from datetime import date
from pathlib import Path
from math import isfinite
import yaml
from backend.analytics.metrics import metrics, find_recurring_risks

FACTORS={'citation_history','classification_history','recurring_deficiencies','recency','severity','negative_trend'}

def load_config(path=None):
    c=yaml.safe_load(Path(path or Path(__file__).resolve().parents[2]/'config/risk_weights.yaml').read_text(encoding='utf-8'))
    if set(c['weights'])!=FACTORS or any(not isfinite(float(v)) or v<0 for v in c['weights'].values()) or sum(c['weights'].values())<=0: raise ValueError('Risk weights must be finite, nonnegative and cover all six factors')
    p=c['parameters']
    if not 0<=p['vai_factor']<=1 or any(p[k]<=0 for k in ['recency_days','recurrence_target','observation_cap']): raise ValueError('Invalid risk parameters')
    b=c['bands']
    if not 0<b['MODERATE']<b['HIGH']<b['CRITICAL']<=100: raise ValueError('Risk band thresholds must be increasing within 0–100')
    return c

def calculate_risk(records,as_of,config=None):
    c=config or load_config(); p=c['parameters']; m=metrics(records,as_of)
    recurrence=find_recurring_risks(records)
    dated_known=[r for r in records if r.get('inspection_date') and (r.get('classification') is not None or r.get('citation_indicator') is not None)]
    adverse=[r for r in dated_known if r.get('classification') in ('OAI','VAI') or r.get('citation_indicator')==1]
    annual=[]
    for y in sorted({r['inspection_year'] for r in records if r.get('inspection_year') is not None}):
        yr=metrics([r for r in records if r.get('inspection_year')==y],as_of)
        if yr['citation_rate'] is not None: annual.append(yr['citation_rate'])
    recency=None
    if dated_known:
        recency=max(0,1-(date.fromisoformat(as_of)-date.fromisoformat(max(r['inspection_date'] for r in adverse))).days/p['recency_days']) if adverse else 0
    factors={
        'citation_history':m['citation_rate'],
        'classification_history':(m['OAI']+p['vai_factor']*m['VAI'])/m['classification_known'] if m['classification_known'] else None,
        'recurring_deficiencies':min(1,max([r['repeat_count'] for r in recurrence],default=0)/p['recurrence_target']) if any(r.get('observation_text') for r in records) else None,
        'recency':recency,
        'severity':min(1,m['average_observations']/p['observation_cap']) if m['average_observations'] is not None else None,
        'negative_trend':max(0,annual[-1]-annual[-2]) if len(annual)>1 else None,
    }
    weights=c['weights']; available=sum(weights[k] for k,v in factors.items() if v is not None)
    components=[{'name':k,'weight':weights[k],'factor':round(v,6) if v is not None else None,
                 'points':round(v*weights[k]*100/available,2) if v is not None and available else None} for k,v in factors.items()]
    raw=sum(v*weights[k]*100/available for k,v in factors.items() if v is not None) if available else None
    score=round(raw,2) if raw is not None else None
    band='INSUFFICIENT DATA' if raw is None else next((name for name in ['CRITICAL','HIGH','MODERATE'] if raw>=c['bands'][name]),'LOW')
    return {'score':score,'band':band,'components':components,'coverage_pct':round(available/sum(weights.values())*100,2),
            'missing_factors':[k for k,v in factors.items() if v is None], 'as_of':as_of,'methodology_version':c['version'],
            'metrics':m,'limitations':['Heuristic prioritization score; not an FDA rating.','Severity uses observation count as a burden proxy.','Low coverage does not establish low risk.']}

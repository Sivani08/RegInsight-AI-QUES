"""Deterministic signals and explicitly exploratory monthly rate forecasting."""
import json,math
from datetime import date
from collections import defaultdict
from backend.services import qc_data as data
from backend.cache.redis_cache import get_cache
RULES=data.ROOT/'config/qc_rules.json'
def month_number(m):return int(m[:4])*12+int(m[5:])-1
def month_label(n):return f'{n//12:04}-{n%12+1:02}'
def predict(values,h=1):
    n=len(values);mx=(n-1)/2;my=sum(values)/n
    slope=sum((i-mx)*(v-my) for i,v in enumerate(values))/sum((i-mx)**2 for i in range(n)) if n>1 else 0.
    return max(0.,min(1.,my+slope*((n-1+h)-mx)))
def forecast(series,as_of,min_months=6,horizon=3):
    eligible=[r for r in series if r['month']<as_of[:7]]
    if len(eligible)<min_months:return {'status':'insufficient_history','reason':'At least six complete monthly periods are required.'}
    if any(month_number(b['month'])-month_number(a['month'])!=1 for a,b in zip(eligible,eligible[1:])):return {'status':'missing_periods','reason':'Missing months are not silently filled with zeros.'}
    values=[r['rate'] for r in eligible];errors=[];naive=[]
    for i in range(3,len(values)):
        errors.append(abs(predict(values[:i])-values[i]));naive.append(abs(values[i-1]-values[i]))
    mae=sum(errors)/len(errors);baseline=sum(naive)/len(naive)
    # If trend does not beat last-value holdout performance, use the simpler baseline.
    method='linear_trend' if mae<baseline else 'last_value'
    error=mae if method=='linear_trend' else baseline
    end=month_number(eligible[-1]['month'])
    points=[]
    for h in range(1,horizon+1):
        value=predict(values,h) if method=='linear_trend' else values[-1]
        points.append({'month':month_label(end+h),'rate':round(value,6),'historical_error_low':round(max(0,value-error),6),'historical_error_high':round(min(1,value+error),6)})
    return {'status':'exploratory','stale_history':end<month_number(as_of[:7])-1,'method':method,'training_end':eligible[-1]['month'],'complete_months':len(values),'backtest_folds':len(errors),'linear_mae':mae,'last_value_mae':baseline,'points':points,'notice':'Operational rate projection, not inspection outcome probability. Error bands are historical MAE, not calibrated confidence intervals. Horizons start after the last observed month.'}
def analyze(dataset_id,study=None,as_of=None):
    as_of=as_of or date.today().isoformat();date.fromisoformat(as_of)
    rules=json.loads(RULES.read_text(encoding='utf-8-sig'));cache=get_cache()
    key=cache.key('qc-signals',[dataset_id,study,as_of,data.digest(rules)])
    hit=cache.get(key)
    if isinstance(hit,dict) and hit.get('dataset',{}).get('id')==dataset_id:return hit
    meta,records=data.rows(dataset_id,study);groups=defaultdict(list)
    for r in records:
        if r['month']<as_of[:7]:groups[(r['study'],r['site'],r['metric'])].append(r)
    signals=[];series=[]
    for (study_id,site,metric),rs in sorted(groups.items()):
        rs.sort(key=lambda r:r['month']);history=[{**r,'rate':r['numerator']/r['denominator']} for r in rs]
        rule=rules['metrics'][metric];latest=history[-1];projection=forecast(history,as_of,rules['forecast_min_months'],rules['forecast_horizon_months'])
        series.append({'study':study_id,'site':site,'metric':metric,'history':history,'forecast':projection})
        future=[p for p in projection.get('points',[]) if p['month']>=as_of[:7]]
        reason='threshold_breach' if latest['rate']>rule['threshold'] else 'forecast_threshold' if any(p['rate']>rule['threshold'] for p in future) else None
        if reason:
            identity=[dataset_id,study_id,site,metric,latest['month'],rules['version'],reason]
            signals.append({'id':data.digest(identity)[:24],'study':study_id,'site':site,'metric':metric,'label':rule['label'],'reason':reason,'month':latest['month'],'observed_rate':latest['rate'],'threshold':rule['threshold'],'numerator':latest['numerator'],'denominator':latest['denominator'],'evidence_ids':[r['record_id'] for r in history],'recommendation':rule['action'],'reference':rule['reference'],'review_required':True,'policy_version':rules['version']})
    clusters=[]
    for study_id,metric in sorted({(r['study'],r['metric']) for r in signals}):
        sites=sorted({r['site'] for r in signals if r['study']==study_id and r['metric']==metric})
        if len(sites)>1:clusters.append({'study':study_id,'metric':metric,'sites':sites,'notice':'Shared metric breaches; a common root cause has not been established.'})
    result={'dataset':meta,'as_of':as_of,'study':study,'signals':signals,'series':series,'cross_site_patterns':clusters,'excluded_current_or_future_rows':sum(r['month']>=as_of[:7] for r in records),'policy':rules,'notice':'Demo analytical QC monitoring. No automated action, regulatory readiness certification or clinical inference.'}
    cache.put(key,result);return result

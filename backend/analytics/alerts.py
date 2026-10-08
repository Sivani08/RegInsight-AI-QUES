from datetime import date
from pathlib import Path
import yaml
from backend.analytics.metrics import metrics,find_recurring_risks
from backend.analytics.taxonomy import rule_analysis
from backend.risk.engine import calculate_risk

def site_alerts(records,as_of,risk_config,rules=None):
    rules=rules or yaml.safe_load((Path(__file__).resolve().parents[2]/'config/alert_rules.yaml').read_text(encoding='utf-8'))
    if not records:return []
    risk=calculate_risk(records,as_of,risk_config);alerts=[]
    def add(code,message,ids):
        alerts.append({'code':code,'message':message,'site_key':records[0]['site_key'],
            'company_name':records[0].get('company_name'),'site_name':records[0].get('site_name'),
            'inspection_ids':sorted(ids),'as_of':as_of})
    if risk['band'] in ['HIGH','CRITICAL']:
        add('HIGH_RISK_SITE',f"Site is {risk['band']} at {risk['score']}/100; coverage {risk['coverage_pct']}%.",[r['inspection_id'] for r in records])
    oai=[r for r in records if r.get('classification')=='OAI']
    if len(oai)>=rules['repeated_oai_count']:
        add('REPEATED_OAI',f"{len(oai)} recorded OAI inspections.",[r['inspection_id'] for r in oai])
    years=sorted({r['inspection_year'] for r in records if r.get('inspection_year') is not None})
    if len(years)>=2:
        prev=[r for r in records if r.get('inspection_year')==years[-2]]
        latest=[r for r in records if r.get('inspection_year')==years[-1]]
        a=metrics(prev,as_of);b=metrics(latest,as_of)
        if min(a['citation_known'],b['citation_known'])>=rules['minimum_yearly_known_flags']:
            delta=b['citation_rate']-a['citation_rate']
            if delta>=rules['citation_rate_increase']:
                add('CITATION_RATE_INCREASE',f"Citation rate rose {delta*100:.1f} percentage points between {years[-2]} and {years[-1]}; latest year may be partial.",[r['inspection_id'] for r in prev+latest if r.get('citation_indicator') is not None])
    for theme in find_recurring_risks(records):
        if theme['theme']=='Data Integrity' and theme['count']>=rules['data_integrity_count']:
            add('RECURRING_DATA_INTEGRITY',f"Data Integrity keyword signals appear in {theme['count']} distinct inspections.",theme['inspection_ids'])
    latest_date=max((r['inspection_date'] for r in records if r.get('inspection_date')),default=None)
    new=[r for r in records if r.get('inspection_date')==latest_date and latest_date and
         0<=(date.fromisoformat(as_of)-date.fromisoformat(latest_date)).days<=rules['new_observation_days'] and
         r.get('observation_text') and rule_analysis(r['observation_text'])['severity'] in ['High','Critical']]
    if new:
        add('NEW_HIGH_SEVERITY_SIGNAL',f"Latest inspection text contains a rule-based high-severity signal in {len(new)} inspection(s). Human review required.",[r['inspection_id'] for r in new])
    return alerts

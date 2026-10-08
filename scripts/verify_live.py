"""Live HTTP acceptance check; run against the started application."""
import argparse
import json
import re
import httpx

def verify(base_url, company_search=None):
    with httpx.Client(base_url=base_url,timeout=60) as c:
        root=c.get('/');root.raise_for_status()
        for asset in re.findall(r'(?:src|href)="(/assets/[^"]+)"',root.text): c.get(asset).raise_for_status()
        dashboard=c.get('/api/dashboard');dashboard.raise_for_status();d=dashboard.json()
        quality=c.get('/api/data-quality').json()
        assert d['metrics']['total_inspections']==quality['valid_records']
        companies=c.get('/api/companies',params={'search':company_search} if company_search else {}).json()
        assert companies,'Load inspection records first'
        company=companies[0]['company_name']
        profile=c.get('/api/profile',params={'company':company}).json()
        investigation=c.post('/api/agent/query',json={'question':'Why is this company considered high risk?','company':company})
        investigation.raise_for_status();a=investigation.json();r=a['results'][0]
        assert r['risk']==profile['risk']
        records=[];offset=0
        while True:
            response=c.get('/api/evidence/'+a['analysis_id'],params={'offset':offset,'limit':200})
            response.raise_for_status();e=response.json();records.extend(e['records'])
            if len(records)>=e['record_count']:break
            offset+=200
        assert len(records)==r['risk']['metrics']['total_inspections']
        assert sum(x.get('classification')=='OAI' for x in records)==r['risk']['metrics']['OAI']
        assert len([x for x in records if x.get('citation_indicator') is not None])==r['risk']['metrics']['citation_known']
        assert {t['tool'] for t in e['tools']}=={'search_inspections','calculate_risk','analyze_trend','find_recurring_risks','analyze_observation','get_evidence'}
        for endpoint in ['/api/alerts','/api/trends','/api/recurrence','/api/agent/tools','/openapi.json']:
            c.get(endpoint,params={'company':company} if endpoint=='/api/recurrence' else {}).raise_for_status()
        return {'status':'passed','data_label':quality['data_label'],'total_source_rows':quality['total_records'],
            'valid_inspections':quality['valid_records'],'company':company,'risk_score':r['risk']['score'],'risk_band':r['risk']['band'],
            'evidence_records':len(records),'analysis_id':a['analysis_id'],'tool_count':len(e['tools']),
            'frontend_assets':'served successfully','browser_click_test':'not executed','database':'SQLite','recurrence_scope':company,
            'paid_provider_live_test':'not executed'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8000');p.add_argument('--output');p.add_argument('--company-search',help='Select a company with observation text to exercise all six tools')
    args=p.parse_args();result=verify(args.base_url,args.company_search);text=json.dumps(result,indent=2);print(text)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text,encoding='utf-8')

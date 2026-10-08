import json,time,urllib.request
from pathlib import Path
BASE='http://127.0.0.1:8018'
report={}
def req(path,body=None):
 start=time.perf_counter()
 with urllib.request.urlopen(urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'}),timeout=180) as r:result=json.load(r)
 report[path+((': '+body['question']) if body else '')]={'seconds':round(time.perf_counter()-start,3),'status':200}
 return result
x=req('/api/dashboard');assert x['metrics']['total_inspections']==274886 and x['site_total']==133375
for focus in ['overall_dashboard','inspection_activity','classification_distribution','citation_oai_trend','risk_distribution','sites_to_investigate','recurring_risk_signals','observation_intelligence','data_quality']:
 r=req('/api/agent/dashboard-query',{'question':'What stands out in this graph?','focus':focus,'limit':3})
 report['focus:'+focus]={'status':200,'evidence_rows':len(r['layers']['evidence_and_limitations']['records'])}
 if focus=='observation_intelligence':assert r['layers']['metrics']['observation_count']==280114
r=req('/api/agent/dashboard-query',{'question':'Which sites have the highest risk?','limit':3})
w=req('/api/agent/dashboard-query',{'question':'Why is the first one high?','context':r['context']})
assert w['layers']['metrics']['risk_score']==r['supporting_data'][0]['risk']['score']
assert w['layers']['evidence_and_limitations']['records'][0]['source_file']
Path('docs/upgrade-real-smoke.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

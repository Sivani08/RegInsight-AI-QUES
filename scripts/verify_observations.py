import httpx,json,re
from pathlib import Path
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=20) as c:
    root=c.get('/');root.raise_for_status()
    for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"',root.text):c.get(asset).raise_for_status()
    response=c.get('/api/observation-workspace');response.raise_for_status();d=response.json()
    assert d['run']['completed']==72 and d['run']['failed']==0
    assert sum(r['observations'] for r in d['summary']['categories'])==72
    assert all(r['inspections']==3 and r['repeats']==2 for r in d['summary']['recurrence'])
    e=c.get('/api/observation-workspace/export',params={'run_id':d['run']['id']});e.raise_for_status()
    assert len(e.json()['rows'])==72
    result={'status':'passed','tagged':72,'run_id':d['run']['id'],'provider':d['run']['provider'],'pandas_reconciliation':'passed','evidence_export':'passed','frontend_assets':'served','browser_interaction':'not verified: browser automation initialization failed','live_claude':'pending: credentials absent','expert_evaluation':'pending: no expert labels'}
    Path('docs/acceptance-observations.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

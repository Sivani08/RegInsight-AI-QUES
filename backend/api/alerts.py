from collections import defaultdict
from fastapi import APIRouter,Request
from backend.analytics.alerts import site_alerts
router=APIRouter()
@router.get('/api/alerts')
def alerts(request:Request,company:str|None=None):
    s=request.app.state.service
    grouped=defaultdict(list)
    if s.info().get('mart_ready') and not company:
        for entity in s.entities(limit=20):
            grouped[entity['key']]=s.store.search(site=entity['key'],lightweight=True)
    else:
        for r in s.store.search(company=company,lightweight=True): grouped[r['site_key']].append(r)
    return [a for records in grouped.values() for a in site_alerts(records,s.info()['as_of'],s.config)]

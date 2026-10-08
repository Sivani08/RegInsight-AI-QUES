"""Bounded routing to persisted, deterministic observation intelligence tools."""
import re,uuid
from datetime import datetime,timezone
from backend.tools.observation_tools import ObservationTools
from backend.analytics.intelligence_taxonomy import THEME_NAMES
from backend.services import observation_intelligence as s

def investigate(service,question,company=None,site=None):
    q=question.lower();tools=ObservationTools(service)
    run=s.latest();scope={'run_id':run['id']}
    if company:scope['company']=company
    if site:scope['site']=site
    # Resolve only exact legal-name mentions; context is retained otherwise.
    names=[n for n in service.company_names() if len(n)>4 and re.search(r'(?<!\w)'+re.escape(n.lower())+r'(?!\w)',q)] if not ('this company' in q or 'this site' in q) else []
    names=[n for n in names if not any(n.lower() in x.lower() and len(x)>len(n) for x in names)]
    if len(names)>1:raise ValueError('Select one company for an observation investigation')
    if names:scope={**{k:v for k,v in scope.items() if k!='site'},'company':names[0]}
    found=[t for t in THEME_NAMES if t.lower() in q]
    if found:scope['theme']=max(found,key=len)
    years=[int(y) for y in re.findall(r'\b(?:FY\s*)?((?:19|20)\d{2})\b',question,re.I)]
    if years:scope.update(start_year=min(years),end_year=max(years))
    observation=re.search(r'\b(OBS-[a-f0-9]{32}(?:-VAR-[a-f0-9]+)?|DEMO-\d-\d{4}-\d{2})\b',question,re.I)
    if observation:scope['observation_id']=observation.group(1)
    semantic_group=re.search(r'\bGRP-[a-f0-9]{20}\b',question,re.I)
    if semantic_group:scope['group_id']=semantic_group.group(0)
    if 'human review' in q:scope['review_required']=True
    if 'annual' in q or 'benchmark' in q:scope.update(grain='annual_template',dataset='annual')
    results={};severities=[v for v in ['High','Critical','Medium','Low'] if re.search(r'\b'+v.lower()+r'\b',q)]
    if 'similar' in q:
        if not observation:raise ValueError('Provide an observation ID for similarity evidence')
        results['similar']=tools.call('find_similar_observations',observation_id=scope['observation_id'],run_id=run['id'],grain=scope.get('grain','inspection'))
    elif severities:
        for severity in severities:results[severity]=tools.call('get_observation_tags',**scope,severity=severity)
    else:results['observations']=tools.call('get_observation_tags',**scope)
    if 'semantic group' in q:results['semantic_groups']=tools.call('get_semantic_groups',**scope)
    if 'severity distribution' in q:results['severity_distribution']=tools.call('get_severity_distribution',**scope)
    if 'human review' in q:results['human_review']=tools.call('get_review_observations',**scope)
    group='company' if 'companies' in q or 'by company' in q else 'year' if years or 'increas' in q or 'fiscal year' in q else 'site' if 'sites' in q or 'by site' in q else 'theme'
    results['recurrence']=tools.call('find_recurring_themes',**scope,group_by=group,limit=1000 if group=='year' else 200)
    if 'repeated' in q and group in ('company','site'):
        results['recurrence']['groups']=[r for r in results['recurrence']['groups'] if r['inspection_count']>1]
    if 'increas' in q and years:
        baseline=min(years);end=max(years);rows=results['recurrence']['groups'];themes={r['theme'] for r in rows}
        results['theme_changes']=[{'theme':t,'start_year':baseline,'end_year':end,'start_inspections':next((r['inspection_count'] for r in rows if r['theme']==t and r['year']==baseline),0),'end_inspections':next((r['inspection_count'] for r in rows if r['theme']==t and r['year']==end),0)} for t in sorted(themes)]
        for r in results['theme_changes']:r['change']=r['end_inspections']-r['start_inspections']
        results['theme_changes'].sort(key=lambda r:-r['change'])
    identifier=str(uuid.uuid4());evidence=list({r['observation_id']:r for value in results.values() if isinstance(value,dict) for r in value.get('records',[])}.values())
    payload={'analysis_id':identifier,'question':question,'mode':'observation_intelligence','created_at':datetime.now(timezone.utc).isoformat(),'dataset_id':run['id'],'data_label':'OBSERVATION INTELLIGENCE â€” '+run['dataset'],'as_of':run['created_at'][:10],'methodology':service.config,'results':[],'theme_changes':[],'observation_intelligence':results,'tools':tools.trace,'records':evidence,'limitations':['All counts are deterministic SQL aggregates over the selected corpus snapshot.','Evidence lists are paginated samples; full scope and run ID are recorded.','Similarity indicates related text, not regulatory equivalence.','AI severity does not change the original risk formula.']}
    service.store.save_evidence(identifier,payload);tools.call('get_evidence',analysis_id=identifier);service.store.update_evidence_trace(identifier,tools.trace)
    return {**{k:v for k,v in payload.items() if k!='records'},'tools':tools.trace,'evidence_count':len(evidence)}


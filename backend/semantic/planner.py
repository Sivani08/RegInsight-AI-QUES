import re
from .models import QueryPlan, Filters
from .resolver import resolve
DEFAULTS={'overall_dashboard':['total_inspections','oai_rate','high_risk_sites'],'inspection_activity':['total_inspections'],
 'classification_distribution':['nai_count','vai_count','oai_count'],'citation_oai_trend':['citation_rate','oai_rate'],
 'risk_distribution':['high_risk_sites','critical_risk_sites'],'sites_to_investigate':['high_risk_sites'],
 'recurring_risk_signals':['recurring_themes'],'observation_intelligence':['observation_count','severity_distribution'],
 'data_quality':['total_inspections']}
def plan(request, previous=None, latest_year=None):
    q=request.question.casefold(); focus=request.focus; filters=request.filters.model_dump(exclude_none=True,mode='json')
    intent='summary'; selected=resolve(q); dimensions=[]; limit=request.limit
    if previous:
        old=previous.get('semantic_plan',{})
        # Client filters are authoritative. A changed dashboard scope invalidates old references.
        old_base=previous.get('dashboard_filters',{})
        if old_base != filters: previous=None
    if previous and re.search(r'\b(this|that|these|its|similar|first one|previous|how did|evidence|why|show the inspections|show the records)\b',q):
        old=previous['semantic_plan']; focus=old['focus']; selected=selected or old['metrics']
        filters={**old.get('filters',{}),**filters}
        if re.search(r'first one|this site|that site|this company|this risk score',q):
            refs=previous.get('result_references',[])
            if refs:
                if 'this company' in q:filters.pop('site',None);filters['company']=refs[0]['company']
                else:filters['site']=refs[0]['key']
                focus='sites_to_investigate'; selected=['risk_score']; intent='risk_explanation'
            elif old.get('filters',{}).get('site'): filters['site']=old['filters']['site'];selected=['risk_score'];intent='risk_explanation'
            else:raise ValueError('No selected site in this context. Ask for highest risk sites first.')
        if 'this theme' in q and previous.get('theme_references'):
            filters['theme']=previous['theme_references'][0];focus='recurring_risk_signals'
        if 'similar' in q and previous.get('group_references'):
            filters['semantic_group']=previous['group_references'][0];focus='observation_intelligence';selected=['observation_count'];intent='observation'
    elif re.search(r'first one|this site|that site|this company',q) and not any(k in filters for k in ('site','company')):
        raise ValueError('Select a company/site or ask for highest risk sites first.')
    if re.search(r'how (did|was|is)|calculate|methodology',q):intent='methodology'
    elif 'evidence' in q or 'supports that' in q:intent='evidence'
    elif re.search(r'show (the )?inspections|show (the )?records',q):intent='detail'
    elif intent!='risk_explanation':
        if re.search(r'highest risk|high risk facilities|top (five|\d+)|rank|sites needing attention|sites.*investigate',q):
            intent='ranking';focus='sites_to_investigate';selected=['high_risk_sites']
        elif re.search(r'why.*(high|risk)|risk factors|contribute.*score',q):
            intent='risk_explanation';focus='sites_to_investigate';selected=['risk_score']
        elif any(m in selected for m in ('recurring_themes','recurrence_count')):
            intent='recurrence';focus='recurring_risk_signals';selected=[m for m in selected if m in ('recurring_themes','recurrence_count')]
        elif any(m in selected for m in ('observation_count','severity_distribution','review_required_count')):
            intent='observation';focus='observation_intelligence'
        elif re.search(r'trend|year|changed|increase|decrease|moved|movement|move together|highest|compare|over time',q):
            intent='trend_analysis'; dimensions=['year']
            if focus=='overall_dashboard':focus='citation_oai_trend' if any(m in selected for m in ('oai_rate','citation_rate')) else 'inspection_activity'
        elif selected and all(m in ('oai_count','vai_count','nai_count') for m in selected):focus='classification_distribution'
    if 'split' in q or 'classification dominates' in q:
        focus='classification_distribution';selected=['nai_count','vai_count','oai_count']
    if focus in ('recurring_risk_signals','observation_intelligence') and re.search(r'which sites|sites repeatedly',q):dimensions=['site']
    if focus=='recurring_risk_signals' and re.search(r'increasing|decreasing|over time',q):intent='trend_analysis';dimensions=['year']
    if 'top five' in q:limit=5
    match=re.search(r'\btop (\d+)\b',q)
    if match:limit=int(match[1])
    years=[int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b',q)]
    if len(years)==1:filters.update(year=years[0]);filters.pop('start_year',None);filters.pop('end_year',None)
    elif len(years)==2:filters.pop('year',None);filters.update(start_year=years[0],end_year=years[1])
    comparison='previous_period' if re.search(r'previous|last year|latest year|changed',q) else None
    if comparison and latest_year and not years:
        end=filters.pop('year',None) or filters.get('end_year') or latest_year
        filters.update(start_year=end-1,end_year=end)
        if intent not in ('methodology','evidence','risk_explanation'):intent='trend_analysis';dimensions=['year']
    if not selected and focus=='overall_dashboard' and not re.search(r'stand|insight|portfolio|summari|dashboard|recent|investigate|graph',q):
        raise ValueError('Ask about inspection counts, classifications, trends, site risk, observations or evidence.')
    return QueryPlan(intent=intent,focus=focus,metrics=selected or DEFAULTS[focus],dimensions=dimensions,
                     filters=Filters(**filters),comparison=comparison,limit=limit,offset=request.offset)

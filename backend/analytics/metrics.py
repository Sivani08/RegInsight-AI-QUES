from collections import Counter, defaultdict
from datetime import date
from backend.analytics.taxonomy import themes

def ratio(n,d): return round(n/d,6) if d else None

def metrics(records,as_of):
    known=[r for r in records if r.get('citation_indicator') is not None]
    classified=[r for r in records if r.get('classification') in ('OAI','VAI','NAI')]
    counts=Counter(r.get('classification') or 'Unknown' for r in records)
    observations=[r['observation_count'] for r in records if r.get('observation_count') is not None]
    dated=[r for r in records if r.get('inspection_date')]
    years={r.get('inspection_year') for r in dated}
    return {'total_inspections':len(records),'citation_positive':sum(r['citation_indicator'] for r in known) if known else None,
        'citation_known':len(known),'citation_rate':ratio(sum(r['citation_indicator'] for r in known),len(known)),
        'OAI':counts['OAI'],'VAI':counts['VAI'],'NAI':counts['NAI'],'Unknown':counts['Unknown'],
        'classification_known':len(classified),'oai_rate':ratio(counts['OAI'],len(classified)),
        'average_observations':ratio(sum(observations),len(observations)), 'observations_known':len(observations),
        'inspection_frequency':ratio(len(dated),len(years)), 'frequency_unit':'inspections per observed calendar year',
        'recent_inspections':sum(0<=(date.fromisoformat(as_of)-date.fromisoformat(r['inspection_date'])).days<=365 for r in dated),
        'dated_inspections':len(dated),'posted_citation_inspections':sum(r.get('posted_citation_indicator') or 0 for r in records) if any(r.get('posted_citation_indicator') is not None for r in records) else None,'available_citation_rows':sum(r.get('available_citation_count') or 0 for r in records) if any(r.get('available_citation_count') is not None for r in records) else None}

def find_recurring_risks(records,group_by=None):
    if group_by and group_by not in ['inspection_year','company_name','site_key','country','product_type']: raise ValueError('Unsupported recurrence grouping')
    buckets=defaultdict(set)
    for r in records:
        for theme in themes(r.get('observation_text')):
            buckets[(theme,str(r.get(group_by) or 'Unknown') if group_by else 'All')].add(r['inspection_id'])
    return sorted([{'theme':theme,'group':group,'count':len(ids),'repeat_count':max(0,len(ids)-1),'inspection_ids':sorted(ids)} for (theme,group),ids in buckets.items()],key=lambda x:(-x['count'],x['theme'],x['group']))

def analyze_trend(records,as_of,config,theme=None,start_year=None,end_year=None):
    from backend.risk.engine import calculate_risk
    records=[r for r in records if not theme or theme in themes(r.get('observation_text'))]
    years=sorted({r['inspection_year'] for r in records if r.get('inspection_year') is not None})
    result=[]
    for year in years:
        if (start_year and year<start_year) or (end_year and year>end_year): continue
        cutoff=min(f'{year}-12-31',as_of)
        current=[r for r in records if r.get('inspection_year')==year]
        history=[r for r in records if r.get('inspection_date') and r['inspection_date']<=cutoff]
        risk=calculate_risk(history,cutoff,config)
        result.append({'year':year,**metrics(current,cutoff),'risk_score':risk['score'],'risk_coverage_pct':risk['coverage_pct'],
            'recurring_themes':find_recurring_risks(current),'partial_year':cutoff<f'{year}-12-31'})
    return result

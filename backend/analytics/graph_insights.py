"""Chart narratives derived only from the same aggregates rendered by the UI."""
def graph_insights(metrics,trend,bands=None,as_of=None):
    bands=bands or {};result={}
    total=metrics.get('total_inspections',0)
    if not total:
        return {focus:{'headline':'No inspections match the selected filters.','detail':'Change the filters to view this chart. No rate or trend can be inferred.'} for focus in ('inspection_activity','classification_distribution','citation_oai_trend','risk_distribution')}
    years=sorted(trend,key=lambda r:r['year'])
    complete=[r for r in years if not r.get('partial_year')]
    latest=years[-1] if years else None
    partial=bool(latest and latest.get('partial_year'))
    if latest:
        headline=f"{latest['total_inspections']:,} inspections recorded in {latest['year']}"+(' so far.' if partial else '.')
        detail=f"{latest['year']} is partial as of {as_of}; do not compare its count with a full year." if partial else 'Counts represent the selected inspection scope.'
        if len(complete)>=2:
            previous,current=complete[-2:];change=current['total_inspections']-previous['total_inspections']
            direction='more' if change>0 else 'fewer' if change<0 else 'the same number of'
            detail+=f" Latest complete years: {current['year']} has {abs(change):,} {direction} inspections than {previous['year']}." if change else f" {current['year']} and {previous['year']} have equal inspection counts."
        result['inspection_activity']={'headline':headline,'detail':detail}
    else:result['inspection_activity']={'headline':'No dated inspections are available.','detail':f'{total:,} records match, but a yearly trend cannot be calculated.'}
    counts={k:metrics.get(k,0) for k in ('NAI','VAI','OAI','Unknown')}
    maximum=max(counts.values());leading=[k for k,v in counts.items() if v==maximum]
    result['classification_distribution']={'headline':f"{' / '.join(leading)} {'is the largest classification' if len(leading)==1 else 'are tied for the largest classification'}: {maximum:,} inspections ({maximum/total:.1%} of all matching records).",'detail':f"NAI {counts['NAI']:,} · VAI {counts['VAI']:,} · OAI {counts['OAI']:,} · Unknown {counts['Unknown']:,}. OAI rate uses only NAI, VAI and OAI as its denominator."}
    rate_row=latest or metrics;rate=rate_row.get('oai_rate');year_label=f" in {latest['year']}" if latest else ''
    headline=f"OAI rate{year_label}: {rate:.2%}." if rate is not None else 'OAI rate is unavailable: no known classifications in the latest period.'
    available=any(r.get('citation_rate') is not None for r in years) if years else metrics.get('citation_rate') is not None
    detail='Citation rate is unavailable: citation-indicator denominators were not supplied. Posted citations cannot replace them.' if not available else 'Rates use known denominators in each period; missing values are not zeros.'
    if partial:detail+=f" {latest['year']} is partial; movements do not imply a matched year-to-date comparison."
    result['citation_oai_trend']={'headline':headline,'detail':detail}
    n=sum(bands.values())
    result['risk_distribution']={'headline':f"{bands.get('HIGH',0):,} high-risk and {bands.get('CRITICAL',0):,} critical-risk sites out of {n:,} sites.",'detail':'Bands use the existing weighted risk methodology. Check factor coverage before prioritizing; these scores are not FDA determinations.'}
    return result

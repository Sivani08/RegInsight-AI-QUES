VERSION = 'dashboard-semantics-1.0'
METRICS = {
 'total_inspections':('Inspection count',['inspection volume','number of inspections','inspection count','total inspections']),
 'citation_positive_inspections':('Inspections with a known positive citation indicator',['citation positive']),
 'citation_rate':('Positive citations / inspections with a known citation indicator',['citation rate','citation percentage']),
 'posted_citations':('Available posted citation source rows; not a denominator for citation rate',['posted citations']),
 'nai_count':('No Action Indicated inspections',['nai','no action']),
 'vai_count':('Voluntary Action Indicated inspections',['vai','voluntary action']),
 'oai_count':('Official Action Indicated inspections',['oai inspections','official action','oai count','oai']),
 'oai_rate':('OAI inspections / inspections classified NAI, VAI or OAI',['official action rate','oai percentage','oai rate']),
 'unique_sites':('Distinct canonical site identifiers',['unique sites','site count']),
 'risk_score':('Existing deterministic weighted risk score; available factors only',['risk score','factors','why is']),
 'risk_band':('Band from the existing risk thresholds',['risk band']),
 'high_risk_sites':('Sites in HIGH band',['high risk facilities','highest risk sites','highest risk','sites needing attention','top five','top sites']),
 'critical_risk_sites':('Sites in CRITICAL band',['critical risk sites']),
 'recurring_themes':('Themes found in more than one distinct inspection',['repeated observations','recurring problems','repeated themes','recurring themes','recurrence','themes recur','theme occurs']),
 'recurrence_count':('Distinct inspections beyond the first for a theme',['recurrence count']),
 'observation_count':('Observation records in the selected inspection-grain snapshot',['observation count','observations','common observation themes']),
 'severity_distribution':('Snapshot observation counts grouped by analytical severity',['severity distribution']),
 'review_required_count':('Snapshot observations without an Approve or Modify latest review',['require review','review required','need review'])
}
FOCUSES = ['overall_dashboard','inspection_activity','classification_distribution','citation_oai_trend',
 'risk_distribution','sites_to_investigate','recurring_risk_signals','observation_intelligence','data_quality']
INTENTS = ['summary','trend_analysis','ranking','risk_explanation','recurrence','observation','evidence','methodology','detail']
DIMENSIONS = {
 'year': ['fiscal year','calendar year'], 'inspection_date':['date'], 'company':['manufacturer','organization'],
 'site':['facility'], 'FEI':['fei_number'], 'country':['country'], 'product':['product_type'],
 'inspection_type':['inspection type'], 'classification':['nai','vai','oai'], 'theme':['theme'],
 'severity':['severity'], 'risk_band':['risk band'], 'semantic_group':['group'], 'dataset':['dataset'], 'grain':['grain']}
SOURCE_FIELDS = {'year':'inspection_year / website_index.year','inspection_date':'inspection_date','company':'company_key / company',
 'site':'site_key / site','FEI':'fei_number','country':'country','product':'product_type','inspection_type':'inspection_type',
 'classification':'classification','theme':'theme','severity':'severity','risk_band':'risk.band','semantic_group':'group_id',
 'dataset':'dataset_id / dataset','grain':'grain'}
FILTER_FIELDS = {'year':['year','start_year','end_year'],'inspection_date':['start_date','end_date'],
 'company':['company'],'site':['site'],'FEI':['fei_number'],'country':['country'],'product':['product_type'],
 'inspection_type':['inspection_type'],'classification':['classification'],'theme':['theme'],
 'severity':['severity'],'risk_band':['risk_band'],'semantic_group':['semantic_group'],'dataset':['dataset'],'grain':['grain']}
OBS_METRICS=['recurring_themes','recurrence_count','observation_count','severity_distribution','review_required_count']
COMPOSITE_ALIASES={'citation and oai rates':['citation_rate','oai_rate'],'citation and oai':['citation_rate','oai_rate'],'nai/vai/oai':['nai_count','vai_count','oai_count']}
def catalog():
    return {'version':VERSION,'metrics':[{'name':k,'definition':v[0],'aliases':v[1]} for k,v in METRICS.items()],
      'dimensions':[{'name':k,'aliases':v,'supported_filters':FILTER_FIELDS[k],
       'valid_operators':['eq','gte','lte'] if k in ('year','inspection_date') else ['eq'],
       'supported_metrics':OBS_METRICS if k in ('theme','severity','semantic_group','grain','dataset') else list(METRICS),
       'source_fields':[SOURCE_FIELDS[k]],'null_handling':'Missing remains unavailable; excluded from known denominators.'} for k,v in DIMENSIONS.items()],
      'focus_areas':FOCUSES,'supported_intents':INTENTS}

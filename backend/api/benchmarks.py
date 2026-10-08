from collections import defaultdict
from fastapi import APIRouter,Request,Query
from sqlalchemy import text
from backend.analytics.taxonomy import themes
router=APIRouter()
def program_name(value):return 'Radiological Health' if value=='Radiologic Health' else value
@router.get('/api/benchmarks')
def benchmarks(request:Request,year:int|None=None,program:str|None=None,search:str='',offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=200)):
    store=request.app.state.store
    info=store.info() or {}
    with store.engine.connect() as conn:
        metadata=conn.execute(text('''
            SELECT payload FROM staging.annual_metadata
            WHERE id=1 AND dataset_id=:dataset_id
        '''),{'dataset_id':info.get('dataset_id')}).scalar_one_or_none()
        if metadata is None:
            return {'available':False,'message':'Annual benchmark workbooks have not been loaded for this PostgreSQL dataset.'}
        rows=[dict(row) for row in conn.execute(text('''
            SELECT year,sheet,source_row,program,cite_id,reference,short,long,frequency
            FROM staging.annual_source ORDER BY year,source_row
        ''' )).mappings()]
    if not rows:return {'available':False,'message':'Annual benchmark workbooks have not been loaded for this PostgreSQL dataset.'}
    sources=metadata.get('sources',[])
    summaries=metadata.get('summaries',[])
    programs=sorted({program_name(r['program']) for r in rows})
    rows=[r for r in rows if (not program or program_name(r['program'])==program)
          and (not search or search.lower() in (r['short']+' '+r['long']+' '+r['reference']).lower())]
    trend=[]
    for y in sorted({r['year'] for r in rows}):
        current=[r for r in rows if r['year']==y]
        trend.append({'year':y,'citation_categories':len(current),'frequency_sum':sum(r['frequency'] for r in current)})
    rows=[r for r in rows if not year or r['year']==year]
    scores=defaultdict(int)
    for r in rows:
        for theme in themes(r['long']) or ['Unclassified']:scores[theme]+=r['frequency']
    ordered=sorted(rows,key=lambda r:(-r['frequency'],r['year'],r['cite_id']))
    controls=[]
    for summary in summaries:
        for number,row in enumerate(summary.get('rows',[]),1):
            clean=[v for v in row if v is not None]
            if clean and isinstance(clean[0],str) and clean[0].startswith('Actual Total'):
                controls.append({'year':summary['year'],'forms_483_in_system':int(clean[1]),'sheet':'Summary','source_row':number})
    return {'available':True,'total':len(rows),'frequency_sum':sum(r['frequency'] for r in rows),'rows':ordered[offset:offset+limit],
        'programs':programs,'trend':trend,'system_totals':controls,
        'themes':[{'theme':k,'frequency':v} for k,v in sorted(scores.items(),key=lambda x:-x[1])],
        'sources':sources,'scope':'Annual industry-level citation frequencies; not company inspection records.',
        'notes':['Frequencies are not counts of unique inspections or Forms 483. One form can cite multiple items and program areas.',
            'Source workbooks exclude some manually prepared Forms 483. System totals are the source-reported unique form counts.',
            'Themes are keyword-derived and may overlap. Do not add theme frequencies as if mutually exclusive.',
            'Company risk scores never use these annual aggregates.']}

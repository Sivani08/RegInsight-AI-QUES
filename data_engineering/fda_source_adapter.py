"""Adapt supplied inspection/project rows and citation rows without multiplying inspections.
Consumes the audited PostgreSQL staging schema produced by source_review.py.
"""
import argparse,hashlib,json
from backend.database.postgres import connection
from collections import Counter,defaultdict
from datetime import date
from itertools import groupby
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import delete
from backend.database.store import Store,inspections,datasets
from data_engineering.pipeline import CANONICAL

CLASS={'No Action Indicated (NAI)':'NAI','Voluntary Action Indicated (VAI)':'VAI','Official Action Indicated (OAI)':'OAI'}
RANK={'NAI':0,'VAI':1,'OAI':2}
INSPECTION_FILE='e4832250-43dc-4c0c-982b-b31f87205869.xlsx'
CITATION_FILE='e00adefd-b9ce-414f-ae04-21c950fb5f27.xlsx'

def canonicalize(group,citations,as_of):
    first=group[0]
    if len({(r['fei'],r['date']) for r in group})!=1: raise ValueError('Conflicting FEI/date for inspection '+first['id'])
    day=date.fromisoformat(first['date'])
    if day>date.fromisoformat(as_of):raise ValueError('Future inspection date')
    classes={CLASS.get(r['classification']) for r in group}
    if None in classes:raise ValueError('Unknown source classification')
    projects=sorted({r['project'] for r in group if r['project']})
    products=sorted({r['product'] for r in group if r['product']})
    classification=max(classes,key=RANK.get)
    for c in citations:
        if (c['id'],c['fei'],c['date'])!=(first['id'],first['fei'],first['date']):raise ValueError('Citation identity mismatch')
    raw={'inspection_file':INSPECTION_FILE,'sheet':'Sheet1',
         'inspection_rows':[{'source_row':r['source_row'],'record':json.loads(r['raw'])} for r in group],
         'citation_file':CITATION_FILE,'citation_rows':citations}
    text='\n\n'.join(c['long'] or c['short'] or '' for c in citations) or None
    company=' '.join((first['company'] or '').split())
    return {'inspection_id':first['id'],'fei_number':first['fei'],'company_name':company,'company_key':company.casefold(),
        'site_key':first['fei'],'site_name':'FEI '+first['fei']+' · '+(first['city'] or 'Location unavailable'),'site_name_derived':True,
        'country':first['country'],'city':first['city'],'state':first['state'],'inspection_date':day.isoformat(),
        'fiscal_year':first['fy'],'inspection_year':day.year,'inspection_month':day.month,'inspection_recency':(date.fromisoformat(as_of)-day).days,
        'product_type':' | '.join(products),'product_types':products,'project_area':' | '.join(projects),'project_areas':projects,
        'inspection_type':None,'classification':classification,'classification_basis':'Worst recorded project classification (OAI > VAI > NAI)',
        'project_classifications':[{'project_area':r['project'],'classification':CLASS[r['classification']],'source_row':r['source_row']} for r in group],
        'citation_flag':None,'citation_indicator':None,'posted_citation_indicator':int(any(r['posted']=='Yes' for r in group)),
        'observation_count':None,'available_citation_count':len(citations),'observation_text':text,
        'observation_count_basis':'Not supplied. Available citation rows are retained separately; absence is not proof of no observations.',
        'OAI_indicator':int(classification=='OAI'),'VAI_indicator':int(classification=='VAI'),
        'source_row':str(first['source_row']),'source_record':json.dumps(raw,ensure_ascii=False),
        'source_project_rows':len(group),'rejection_reason':'','data_origin':'user_supplied'}

def import_reviewed(staging,review,output,as_of):
    report=json.loads(Path(review).read_text(encoding='utf-8'));out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    if staging!='staging':raise ValueError('Use the PostgreSQL staging schema')
    store=Store()
    if store.info():raise ValueError('Inspection data already exists; import into a clean database and reconcile before switching.')
    with connection('staging') as src:
        indexed=[];arrow_batch=[];writer=None;n=0;missing=Counter();classes=Counter();posted=0
        # Ordered merge avoids one SQL query per inspection and keeps source extraction bounded.
        cite_iter=iter(groupby(src.execute('SELECT * FROM citation_source ORDER BY id,source_row'),lambda r:r['id']))
        next_cite=next(cite_iter,None)
        with store.engine.begin() as conn:
            conn.execute(delete(inspections));conn.execute(delete(datasets))
            for inspection_id,rows in groupby(src.execute('SELECT * FROM inspection_source ORDER BY id,source_row'),lambda r:r['id']):
                group=[dict(r) for r in rows]
                citations=[]
                if next_cite and next_cite[0]==inspection_id:
                    citations=[dict(r) for r in next_cite[1]];next_cite=next(cite_iter,None)
                elif next_cite and next_cite[0]<inspection_id:raise ValueError('Orphan citation ID')
                r=canonicalize(group,citations,as_of);n+=1
                for k in CANONICAL:
                    if r.get(k) is None or r.get(k)=='':missing[k]+=1
                classes[r['classification']]+=1;posted+=r['posted_citation_indicator']
                indexed.append({k:r.get(k) for k in inspections.c.keys() if k!='payload'}|{'payload':r})
                # Flat payload JSON retains nested source evidence without Arrow schema drift.
                arrow_batch.append({'inspection_id':r['inspection_id'],'fei_number':r['fei_number'],'company_name':r['company_name'],
                    'inspection_date':r['inspection_date'],'classification':r['classification'],'payload_json':json.dumps(r,ensure_ascii=False)})
                if len(indexed)>=1000:
                    conn.execute(inspections.insert(),indexed);indexed=[]
                    table=pa.Table.from_pylist(arrow_batch)
                    if writer is None:writer=pq.ParquetWriter(out/'canonical_inspections.parquet',table.schema)
                    writer.write_table(table);arrow_batch=[]
                    if n%25000==0:print('Canonical inspections',n,flush=True)
            if next_cite:raise ValueError('Unmatched citation rows')
            if indexed:conn.execute(inspections.insert(),indexed)
            if arrow_batch:
                table=pa.Table.from_pylist(arrow_batch)
                if writer is None:writer=pq.ParquetWriter(out/'canonical_inspections.parquet',table.schema)
                writer.write_table(table)
            if writer:writer.close()
            source_total=report['inspection_stats'][0]['rows']
            q={'total_records':source_total,'valid_records':n,'rejected_records':0,'duplicate_records':0,
                'merged_project_rows':source_total-n,'missing_values':{k:missing[k] for k in CANONICAL},
                'missing_value_population':'canonical distinct inspections','invalid_dates':0,'unknown_classifications':0,
                'data_completeness_pct':round(100*(1-sum(missing.values())/(n*len(CANONICAL))),2),
                'as_of':as_of,'engine':'Python audited relational adapter (Spark parity job provided separately)',
                'data_label':'USER-SUPPLIED INSPECTION AND CITATION EXPORTS','source_file':INSPECTION_FILE,
                'dataset_id':hashlib.sha256(json.dumps(report['sources'],sort_keys=True).encode()).hexdigest()[:20],
                'source_files':report['sources'],'missing_columns':['inspection_type','observation_count','citation_flag'],
                'rejected':[],'duplicates':[],'posted_citation_inspections':posted,'classification_counts':dict(classes),
                'notes':['Source rows = distinct inspections + merged project rows. Repeated project rows are preserved, not discarded.',
                    'Classification is the worst recorded project outcome; all project-specific classifications remain in evidence.',
                    'Posted Citations describes publication. True citation rate and total observation counts are unavailable, so affected risk components are excluded.',
                    'Annual FY2023–FY2025 frequencies are separate benchmarks and never joined into company observations.',
                    'Source row numbers, workbook names, and SHA-256 hashes are retained. File provenance was not independently authenticated.']}
            conn.execute(datasets.insert().values(id=1,payload=q))
        (out/'quality.json').write_text(json.dumps(q,indent=2),encoding='utf-8')
        annual=[dict(r) for r in src.execute('SELECT * FROM annual_source ORDER BY year,sheet,source_row')]
        pq.write_table(pa.Table.from_pylist(annual),out/'annual_benchmarks.parquet')
        (out/'annual_benchmarks.json').write_text(json.dumps({'rows':annual,'summaries':report['annual_summaries'],'sources':report['sources'][2:]},ensure_ascii=False),encoding='utf-8')
        print(json.dumps({'inspections':n,'merged_project_rows':source_total-n,'classification':classes,'posted_citation_inspections':posted,'database':'PostgreSQL'},indent=2))
        return q
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--staging',default='staging',choices=['staging']);p.add_argument('--review',required=True);p.add_argument('--output',default='data/real');p.add_argument('--as-of',default='2026-09-10');a=p.parse_args()
    import_reviewed(a.staging,a.review,a.output,a.as_of)

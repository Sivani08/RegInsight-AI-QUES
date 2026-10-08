"""Incremental source normalization. One source row/citation, never one fabricated observation."""
import csv,json,hashlib,os
from pathlib import Path
from datetime import datetime
import pyarrow.parquet as pq
from backend.analytics.intelligence_taxonomy import normalize
from data_engineering.observation_demo import records as demo_records
ROOT=Path(__file__).resolve().parents[1]
DB = 'intelligence'

def db(path=DB):
    from backend.database.postgres import connection
    if str(path) != DB:
        raise ValueError('Observation storage uses the intelligence PostgreSQL schema')
    return connection(DB)

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def parquet_rows(path):
    for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
        for row in batch.to_pylist():yield json.loads(row['payload_json']) if 'payload_json' in row else row

def add(c,row,stats):
    stats['total_records']=stats.get('total_records',0)+1
    reason=row.get('invalid_reason')
    if not isinstance(row.get('text'),str) or not normalize(row.get('text')):
        reason=reason or 'Empty or nontext observation';stats['empty_text_rows']+=1
    if not isinstance(row.get('source'),dict) or not row['source'].get('file'):reason=reason or 'Missing source identity'
    for field in ('inspection_id','observation_id'):
        if row.get(field) is not None and (not isinstance(row[field],str) or not row[field].strip() or len(row[field])>512):reason=reason or 'Invalid record identity'
    if reason:
        c.execute('INSERT INTO quarantine(reason,payload) VALUES (%s,%s)',(reason,json.dumps(row,default=str)))
        stats['invalid_records']=stats.get('invalid_records',0)+1
        return
    stats['valid_records']=stats.get('valid_records',0)+1
    origin=json.dumps(row['source'],sort_keys=True,default=str);meta=row['metadata'];text=normalize(row.get('text'));iid=row.get('inspection_id')
    if iid:
        identity_json=json.dumps(meta,sort_keys=True,default=str)
        old=c.execute('SELECT metadata FROM identities WHERE id=%s',(iid,)).fetchone()
        if old:
            oldmeta=json.loads(old[0]);conflict=any(oldmeta.get(k) and meta.get(k) and normalize(oldmeta[k]).casefold()!=normalize(meta[k]).casefold() for k in ['fei','date','company'])
            if conflict:
                c.execute('INSERT INTO conflicts(identity,existing,incoming,source) VALUES (%s,%s,%s,%s)',(iid,old[0],identity_json,origin));stats['conflicting_records']+=1
                iid=iid+'-CONFLICT-'+digest(identity_json)[:12]
        c.execute('INSERT INTO identities VALUES (%s,%s) ON CONFLICT DO NOTHING',(iid,identity_json))
    h=digest(text);oid=row.get('observation_id') or 'OBS-'+digest(json.dumps([iid or row['source'],row.get('reference'),h,row['grain']],sort_keys=True,default=str))[:32]
    existing=c.execute('SELECT hash,inspection_id,dataset FROM observations WHERE id=%s',(oid,)).fetchone()
    if existing and (existing[0]!=h or existing[1]!=iid or existing[2]!=row['dataset']):
        c.execute('INSERT INTO conflicts(identity,existing,incoming,source) VALUES (%s,%s,%s,%s)',(oid,json.dumps(list(existing)),json.dumps([h,iid,row['dataset']]),origin))
        stats['conflicting_records']+=1;oid+='-VAR-'+digest(json.dumps([h,iid,row['dataset']]))[:12]
    c.execute('INSERT INTO texts VALUES (%s,%s) ON CONFLICT DO NOTHING',(h,text))
    original={**row['source'],'original_text':row.get('text'),'metadata':meta,'source_observation_id':row.get('observation_id')}
    year=meta.get('year');year=int(year) if str(year or '').isdigit() else None
    cur=c.execute('INSERT INTO observations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(oid,h,row['dataset'],row['grain'],iid,meta.get('company'),meta.get('site'),year,meta.get('product'),meta.get('inspection_type'),row.get('frequency'),json.dumps(original,default=str)))
    stats['source_observation_rows']+=1;stats['duplicate_observation_rows']+=cur.rowcount==0
    c.execute('INSERT INTO origins VALUES (%s,%s) ON CONFLICT DO NOTHING',(oid,origin))

def from_inspections(path,dataset):
    for r in parquet_rows(path):
        meta={'fei':r.get('fei_number'),'date':r.get('inspection_date'),'company':r.get('company_name'),'site':r.get('site_key') or r.get('site_name'),'year':r.get('fiscal_year'),'product':r.get('product_type'),'inspection_type':r.get('inspection_type')}
        raw=json.loads(r.get('source_record') or '{}')
        citations=raw.get('citation_rows')
        base={'dataset':dataset,'grain':'inspection','inspection_id':r.get('inspection_id'),'metadata':meta}
        if citations:
            for cite in citations:yield {**base,'text':cite.get('long') or cite.get('short'),'reference':cite.get('reference') or cite.get('act'),'source':{'file':raw.get('citation_file',str(path)),'sheet':cite.get('source_sheet'),'row':str(cite['source_row']) if cite.get('source_row') is not None else None,'citation':cite}}
        else:yield {**base,'text':r.get('observation_text'),'source':{'file':str(path),'row':str(r['source_row']) if r.get('source_row') is not None else None,'inspection_source':raw},'reference':'inspection_text'}

def generic(path):
    if path.suffix.lower()=='.parquet':stream=parquet_rows(path)
    elif path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:yield from generic_rows(csv.DictReader(f),path)
        return
    elif path.suffix.lower()=='.xlsx':
        from openpyxl import load_workbook
        wb=load_workbook(path,read_only=True,data_only=True)
        for ws in wb:
            it=ws.iter_rows(values_only=True);header=next(it,());yield from generic_rows((dict(zip(header,r)) for r in it),path,ws.title)
        wb.close();return
    else:return
    yield from generic_rows(stream,path)

def generic_rows(stream,path,sheet=None):
    for number,r in enumerate(stream,1 if path.suffix.lower()=='.parquet' else 2):
        def pick(*keys):return next((r[k] for k in keys if r.get(k) not in (None,'')),None)
        text=pick('observation_text','Observation Text','Long Description','long')
        if not any(k in r for k in ['observation_text','Observation Text','Long Description','long']):
            yield {'text':None,'invalid_reason':'Unsupported observation schema','source':{'file':str(path),'sheet':sheet,'row':str(number),'record':r}}
            continue
        day=pick('inspection_date','Inspection End Date','Inspection Date')
        if isinstance(day,datetime):day=day.date().isoformat()
        frequency=pick('frequency','Frequency','Frequency of Citations');annual=frequency is not None and not pick('inspection_id','Inspection ID')
        if frequency is not None:
            try:
                if isinstance(frequency,bool) or float(frequency)!=int(frequency) or int(frequency)<0:raise ValueError()
                frequency=int(frequency)
            except (ValueError,TypeError,OverflowError):
                yield {'text':text,'invalid_reason':'Invalid frequency','source':{'file':str(path),'sheet':sheet,'row':str(number),'record':r}}
                continue
        yield {'frequency':int(frequency) if frequency is not None else None,'dataset':str(pick('dataset','Dataset') or 'additional'),'grain':'annual_template' if annual else 'inspection','inspection_id':str(pick('inspection_id','Inspection ID')) if pick('inspection_id','Inspection ID') else None,'observation_id':str(pick('observation_id','Observation ID')) if pick('observation_id','Observation ID') else None,'text':text,'reference':pick('Act/CFR Number','reference'),'metadata':{'fei':str(pick('fei_number','FEI Number','FEI') or '') or None,'date':day,'company':pick('company','company_name','Legal Name','Company'),'site':pick('site','site_key','site_name','Site'),'year':pick('fiscal_year','Fiscal Year'),'product':pick('product','product_type','Product Type','Product'),'inspection_type':pick('inspection_type','Inspection Type')},'source':{'file':str(path),'sheet':sheet,'row':str(number),'record':r}}

def ingest(root=ROOT,path=DB):
    root=Path(root);stats={'source_observation_rows':0,'duplicate_observation_rows':0,'empty_text_rows':0,'conflicting_records':0,'unsupported_inputs':[]}
    with db(path) as c:
        if c.execute('SELECT 1 FROM corpus LIMIT 1').fetchone():raise ValueError('Corpus already loaded; use a new --database path for a new source snapshot. Tagging runs reuse this snapshot.')
        sources=[]
        for rel,label in [('data/real/canonical_inspections.parquet','real'),('data/processed/inspections.parquet','synthetic')]:
            p=root/rel
            if p.exists():sources.append((p,from_inspections(p,label)))
        p=root/'data/real/annual_benchmarks.parquet'
        if p.exists():
            annual_names={2023:'Inspection_Observations_FY23_0.xlsx',2024:'inspection_observations_fy24.xlsx',2025:'inspection_observations_fiscal_year_2025_0.xlsx'}
            sources.append((p,({'dataset':'annual','grain':'annual_template','inspection_id':None,'text':r.get('long') or r.get('short'),'reference':r.get('reference'),'frequency':r.get('frequency'),'metadata':{'year':r['year'],'product':r.get('program')},'source':{'file':annual_names.get(r['year'],str(p)),'sheet':r['sheet'],'row':str(r['source_row']),'record':r}} for r in parquet_rows(p))))
        sources.append(('synthetic observation fixtures',({'dataset':'demo','grain':'inspection','inspection_id':r['inspection_id'],'observation_id':r['observation_id'],'text':r['observation_text'],'metadata':{'company':r['company_name'],'site':r['site_name'],'year':int(r['inspection_date'][:4]),'date':r['inspection_date']},'source':{'file':'data_engineering/observation_demo.py','row':r['observation_id'],'format_reference':r['format_source_url']}} for r in demo_records())))
        from data_engineering.dataset_inventory import sha,source_paths
        source_manifest=root/'data/real/source_evaluation.json'
        audited=json.loads(source_manifest.read_text(encoding='utf-8'))['sources'] if source_manifest.exists() else []
        audited_hashes={r['file']:r['sha256'] for r in audited if
                        (root/('data/real/annual_benchmarks.parquet' if r.get('kind')=='annual_frequency' else 'data/real/canonical_inspections.parquet')).exists()}
        prepared={p.resolve() for p,_ in sources if isinstance(p,Path)}
        excluded={'intelligence','observations','qc','knowledge'}
        extra={p for p in (root/'data').rglob('*') if p.is_file() and p.suffix.lower() in ['.csv','.xlsx','.parquet']
               and not (set(p.relative_to(root/'data').parts[:-1]) & excluded)
               and p.resolve() not in prepared and p.name not in {'rejected.parquet','duplicates.parquet'}}
        if (root/'data/processed/inspections.parquet').exists():extra.discard(root/'data/sample/synthetic_inspections.csv')
        extra.update(p for p in source_paths(root) if p.name not in audited_hashes)
        for p in sorted(extra):
            if p.exists() and p.name in audited_hashes and sha(p)==audited_hashes[p.name]:continue
            if not p.exists():stats['unsupported_inputs'].append({'source':str(p),'error':'Missing input'});continue
            sources.append((p,generic(p)))
        stats['source_fingerprints']={str(name):sha(name) for name,_ in sources if isinstance(name,Path) and name.exists()}

        for name,stream in sources:
            try:
                for row in stream:
                    add(c,row,stats)
                    if stats['source_observation_rows']%25000==0 and stats['source_observation_rows']:print('Normalized',stats['source_observation_rows'],flush=True)
            except (ValueError,OSError,KeyError,TypeError) as e:
                stats['unsupported_inputs'].append({'source':str(name),'error':'Source could not be completely read; inspect original input'})
                c.execute('INSERT INTO quarantine(reason,payload) VALUES (%s,%s)',('Unreadable source',json.dumps({'source_file':str(name),'error_type':type(e).__name__})))
            print('Loaded',str(name),flush=True)
        stats['total_inspections']=c.execute('SELECT count(*) FROM identities').fetchone()[0]
        stats['total_observations']=c.execute('SELECT count(*) FROM observations').fetchone()[0]
        stats['unique_observation_texts']=c.execute('SELECT count(*) FROM texts').fetchone()[0]
        stats.setdefault('invalid_records',0);stats.setdefault('valid_records',0);stats.setdefault('total_records',0)
        stats['duplicates']=stats['duplicate_observation_rows']
        stats['datasets']=[dict(r) for r in c.execute('SELECT dataset,grain,count(*) rows FROM observations GROUP BY dataset,grain')]
        stats['snapshot_id']=digest(json.dumps(stats,sort_keys=True))[:20]
        c.execute('INSERT INTO corpus VALUES (%s,%s)',('quality',json.dumps(stats)))
    return stats

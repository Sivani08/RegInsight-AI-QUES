"""Restore the supplied real snapshots. No fabricated rows or provider calls."""
import gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from backend.database.store import Store,inspections,datasets,ROOT
from data_engineering.intelligence_sources import parquet_rows,db,DB

def restore_observations(source=None):
    """Restore the bundled real snapshot atomically, without provider calls."""
    source = Path(source) if source else ROOT / 'data/intelligence/latest'
    report = json.loads((source / 'report.json').read_text(encoding='utf-8'))
    if report.get('dataset') != 'real' or report.get('status') != 'completed':
        raise ValueError('A completed real observation snapshot is required')
    run_id = report['id']
    statements = {
        'texts': 'INSERT INTO texts(hash,text) VALUES (%s,%s) ON CONFLICT DO NOTHING',
        'observations': '''INSERT INTO observations
            (id,hash,dataset,grain,inspection_id,company,site,year,product,inspection_type,frequency,source)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        'origins': 'INSERT INTO origins(observation_id,origin) VALUES (%s,%s) ON CONFLICT DO NOTHING',
        'cache': 'INSERT INTO cache(key,hash,payload) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
        'assignments': '''INSERT INTO assignments(run_id,hash,cache_key,group_id,similarity,method)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        'members': 'INSERT INTO members(run_id,observation_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
    }
    with db(DB) as current:
        # Snapshot restore is a bounded bulk load. The normal request timeout is
        # intentionally short, but it is too small for the final 280k-row check.
        current.execute("SET LOCAL statement_timeout = '15min'")
        current.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                        ('restore-real-observations',))
        existing = current.execute('SELECT payload FROM runs WHERE id=%s', (run_id,)).fetchone()
        if not existing:
            current.execute('INSERT INTO runs(id,payload) VALUES (%s,%s)', (run_id,json.dumps(report)))
            # COPY into temporary tables avoids one network command per row,
            # while the final inserts retain conflict handling and atomicity.
            columns = {name: statement.split('(', 1)[1].split(')', 1)[0]
                       for name, statement in statements.items()}
            for name, fields in columns.items():
                current.execute(f'CREATE TEMP TABLE restore_{name} ON COMMIT DROP '
                                f'AS SELECT {fields} FROM {name} WITH NO DATA')
            batches = {name: [] for name in statements}
            count = 0
            def flush():
                with current.cursor() as cursor:
                    for name, fields in columns.items():
                        if batches[name]:
                            with cursor.copy(f'COPY restore_{name} ({fields}) FROM STDIN') as copy:
                                for record in batches[name]:
                                    copy.write_row(record)
                            cursor.execute(f'INSERT INTO {name} ({fields}) '
                                           f'SELECT {fields} FROM restore_{name} ON CONFLICT DO NOTHING')
                            cursor.execute(f'TRUNCATE restore_{name}')
                            batches[name].clear()
            with gzip.open(source / 'tags.jsonl.gz', 'rt', encoding='utf-8') as records:
                for line in records:
                    row = json.loads(line)
                    if row.get('dataset') != 'real' or not row.get('source', {}).get('file'):
                        raise ValueError('Snapshot contains non-real data or missing source provenance')
                    observation_id = row['observation_id']
                    text_hash = row['observation_hash']
                    cache_key = 'restored-' + text_hash
                    provenance = json.dumps(row['source'])
                    batches['texts'].append((text_hash,row['normalized_observation']))
                    batches['observations'].append((observation_id,text_hash,'real','inspection',
                        row['inspection_id'],row['company'],row['site'],row.get('fiscal_year'),
                        row.get('product'),row.get('inspection_type'),None,provenance))
                    batches['origins'].append((observation_id,provenance))
                    batches['cache'].append((cache_key,text_hash,json.dumps(row['tag'])))
                    batches['assignments'].append((run_id,text_hash,cache_key,row['group_id'],
                        row['similarity_score'],row['grouping_method']))
                    batches['members'].append((run_id,observation_id))
                    count += 1
                    if count % 10000 == 0:
                        flush()
                    if count % 50000 == 0:
                        print('Restored real observation rows:',count,flush=True)
            flush()
            if count != report['total']:
                raise ValueError('Real snapshot row count does not match its report')
            current.execute('INSERT INTO corpus(key,value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING',
                            ('quality',json.dumps(report['quality'])))
            for name in statements:
                current.execute(f'ANALYZE {name}')
        actual = current.execute('''SELECT count(*) FROM members m JOIN observations o
            ON o.id=m.observation_id WHERE m.run_id=%s AND o.dataset='real' ''', (run_id,)).fetchone()[0]
        if actual != report['total']:
            raise ValueError('Stored real observation snapshot is incomplete')
    from backend.services.website_index import ensure
    ensure(DB,run_id)
    print('Real observation snapshot ready:',actual,flush=True)
    return run_id


def prepare():
    store=Store(allow_fallback=False)
    if not store.info():
        quality=json.loads((ROOT/'data/real/quality.json').read_text(encoding='utf-8'))
        n=0;batch=[]
        with store.engine.begin() as c:
            for row in parquet_rows(ROOT/'data/real/canonical_inspections.parquet'):
                batch.append({'inspection_id':row['inspection_id'],**{k:row.get(k) for k in inspections.c.keys() if k not in ('inspection_id','payload')},'payload':row});n+=1
                if len(batch)>=1000:c.execute(inspections.insert(),batch);batch=[]
            if batch:c.execute(inspections.insert(),batch)
            assert n==quality['valid_records'],(n,quality['valid_records'])
            c.execute(datasets.insert().values(id=1,payload=quality))
        print('Loaded real inspections:',n,flush=True)
    if not store.info().get('mart_ready'):
        from backend.services.mart import build
        build(store)
    restore_observations()
if __name__=='__main__':prepare()

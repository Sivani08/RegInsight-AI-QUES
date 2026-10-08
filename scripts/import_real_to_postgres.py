"""Replace the synthetic PostgreSQL demo with the supplied real inspection exports."""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from sqlalchemy import Column, Integer, MetaData, String, Table, delete, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.store import Store, datasets, inspections

SOURCE = ROOT / 'data' / 'real'
INSPECTIONS_FILE = SOURCE / 'canonical_inspections.parquet'
ANNUAL_FILE = SOURCE / 'annual_benchmarks.parquet'
ANNUAL_JSON = SOURCE / 'annual_benchmarks.json'
QUALITY_FILE = SOURCE / 'quality.json'
BATCH_SIZE = 1000

staging = MetaData()
inspection_source = Table(
    'inspection_source', staging,
    Column('source_row', Integer), Column('id', String), Column('fei', String),
    Column('company', String), Column('city', String), Column('state', String),
    Column('country', String), Column('fy', Integer), Column('date', String),
    Column('classification', String), Column('posted', String), Column('project', String),
    Column('product', String), Column('raw', String), schema='staging')
citation_source = Table(
    'citation_source', staging,
    Column('source_row', Integer), Column('id', String), Column('fei', String),
    Column('company', String), Column('date', String), Column('program', String),
    Column('reference', String), Column('short', String), Column('long', String),
    schema='staging')
annual_source = Table(
    'annual_source', staging,
    Column('year', Integer), Column('sheet', String), Column('source_row', Integer),
    Column('program', String), Column('cite_id', String), Column('reference', String),
    Column('short', String), Column('long', String), Column('frequency', Integer),
    schema='staging')


def as_int(value):
    if value in (None, ''):
        return None
    return int(value)


def flush(conn, table, batch, label, total):
    if batch:
        conn.execute(table.insert(), batch)
        total += len(batch)
        batch.clear()
        if total % 50000 < BATCH_SIZE:
            print(f'Imported {total:,} {label} rows', flush=True)
    return total


def load_inspections(conn, expected):
    parquet = pq.ParquetFile(INSPECTIONS_FILE)
    if parquet.metadata.num_rows != expected:
        raise ValueError(f'Expected {expected:,} canonical inspections; found {parquet.metadata.num_rows:,}.')
    batch = []
    total = 0
    for record_batch in parquet.iter_batches(batch_size=BATCH_SIZE, columns=['payload_json']):
        for value in record_batch.column(0).to_pylist():
            record = json.loads(value)
            if not record.get('inspection_id'):
                raise ValueError('Canonical inspection is missing inspection_id.')
            batch.append({
                'inspection_id': str(record['inspection_id']),
                **{key: record.get(key) for key in inspections.c.keys()
                   if key not in ('inspection_id', 'payload')},
                'payload': record,
            })
        if len(batch) >= BATCH_SIZE:
            total = flush(conn, inspections, batch, 'canonical inspection', total)
    total = flush(conn, inspections, batch, 'canonical inspection', total)
    if total != expected:
        raise ValueError(f'Imported {total:,} canonical inspections; expected {expected:,}.')
    return total


def load_source_rows(conn, expected_inspections, expected_citations):
    parquet = pq.ParquetFile(INSPECTIONS_FILE)
    inspection_batch = []
    citation_batch = []
    inspection_count = citation_count = 0
    for record_batch in parquet.iter_batches(batch_size=500, columns=['payload_json']):
        for value in record_batch.column(0).to_pylist():
            record = json.loads(value)
            source = json.loads(record.get('source_record') or '{}')
            for item in source.get('inspection_rows') or []:
                raw = item.get('record') or {}
                inspection_batch.append({
                    'source_row': as_int(item.get('source_row')),
                    'id': raw.get('Inspection ID'),
                    'fei': raw.get('FEI Number'),
                    'company': raw.get('Legal Name'),
                    'city': raw.get('City'),
                    'state': raw.get('State'),
                    'country': raw.get('Country/Area'),
                    'fy': as_int(raw.get('Fiscal Year')),
                    'date': raw.get('Inspection End Date'),
                    'classification': raw.get('Classification'),
                    'posted': raw.get('Posted Citations'),
                    'project': raw.get('Project Area'),
                    'product': raw.get('Product Type'),
                    'raw': json.dumps(raw, ensure_ascii=False, default=str),
                })
            for item in source.get('citation_rows') or []:
                citation_batch.append({
                    'source_row': as_int(item.get('source_row')),
                    'id': item.get('id'),
                    'fei': item.get('fei'),
                    'company': item.get('company'),
                    'date': item.get('date'),
                    'program': item.get('program'),
                    'reference': item.get('reference'),
                    'short': item.get('short'),
                    'long': item.get('long'),
                })
            if len(inspection_batch) >= BATCH_SIZE:
                inspection_count = flush(conn, inspection_source, inspection_batch,
                                         'inspection source', inspection_count)
            if len(citation_batch) >= BATCH_SIZE:
                citation_count = flush(conn, citation_source, citation_batch,
                                       'citation source', citation_count)
    inspection_count = flush(conn, inspection_source, inspection_batch,
                             'inspection source', inspection_count)
    citation_count = flush(conn, citation_source, citation_batch,
                           'citation source', citation_count)
    if inspection_count != expected_inspections:
        raise ValueError(f'Imported {inspection_count:,} inspection source rows; expected {expected_inspections:,}.')
    if citation_count != expected_citations:
        raise ValueError(f'Imported {citation_count:,} citation rows; expected {expected_citations:,}.')
    return inspection_count, citation_count


def load_annual_rows(conn, expected):
    parquet = pq.ParquetFile(ANNUAL_FILE)
    if parquet.metadata.num_rows != expected:
        raise ValueError(f'Expected {expected:,} annual benchmark rows; found {parquet.metadata.num_rows:,}.')
    batch = []
    total = 0
    for record_batch in parquet.iter_batches(batch_size=BATCH_SIZE):
        for record in record_batch.to_pylist():
            batch.append({key: record.get(key) for key in (
                'year', 'sheet', 'source_row', 'program', 'cite_id',
                'reference', 'short', 'long', 'frequency')})
        if len(batch) >= BATCH_SIZE:
            total = flush(conn, annual_source, batch, 'annual benchmark', total)
    total = flush(conn, annual_source, batch, 'annual benchmark', total)
    if total != expected:
        raise ValueError(f'Imported {total:,} annual benchmark rows; expected {expected:,}.')
    metadata = json.loads(ANNUAL_JSON.read_text(encoding='utf-8'))
    conn.execute(text('''
        INSERT INTO staging.annual_metadata (id, dataset_id, payload)
        VALUES (1, :dataset_id, CAST(:payload AS jsonb))
        ON CONFLICT (id) DO UPDATE SET dataset_id=EXCLUDED.dataset_id, payload=EXCLUDED.payload
    '''), {
        'dataset_id': json.loads(QUALITY_FILE.read_text(encoding='utf-8'))['dataset_id'],
        'payload': json.dumps({
            'sources': metadata.get('sources', []),
            'summaries': metadata.get('summaries', []),
        }, ensure_ascii=False),
    })
    return total


def import_data():
    for path in (INSPECTIONS_FILE, ANNUAL_FILE, ANNUAL_JSON, QUALITY_FILE):
        if not path.is_file():
            raise FileNotFoundError(f'Required prepared real-data input is missing: {path}')
    quality = json.loads(QUALITY_FILE.read_text(encoding='utf-8'))
    expected_inspections = int(quality['valid_records'])
    expected_inspection_rows = sum(
        int(item['rows']) for item in quality['source_files'] if item['kind'] == 'inspections')
    expected_citations = sum(
        int(item['rows']) for item in quality['source_files'] if item['kind'] == 'citations')
    expected_annual = sum(
        int(item['rows']) for item in quality['source_files'] if item['kind'] == 'annual_frequency')
    if not all((expected_inspections, expected_inspection_rows, expected_citations, expected_annual)):
        raise ValueError('The dataset manifest does not contain nonzero inspection, citation, and annual counts.')
    annual_meta = json.loads(ANNUAL_JSON.read_text(encoding='utf-8'))
    if len(annual_meta.get('rows', [])) != expected_annual:
        raise ValueError('Annual benchmark JSON and source manifest row counts do not match.')

    store = Store(allow_fallback=False)
    current = store.info()
    current_count = store.search(count_only=True)
    if current and current.get('dataset_id') == quality.get('dataset_id'):
        if current_count != expected_inspections:
            raise ValueError('PostgreSQL dataset ID matches the source, but its inspection count does not.')
        print(f'PostgreSQL already contains dataset {quality["dataset_id"]}; refreshing source tables.', flush=True)
    elif current and current.get('data_label') != 'SYNTHETIC DEMONSTRATION DATA':
        raise ValueError('Refusing to replace an existing non-demo PostgreSQL dataset with this source.')
    else:
        print(f'Importing {expected_inspections:,} canonical inspections to PostgreSQL.', flush=True)

    if not current or current.get('dataset_id') != quality.get('dataset_id'):
        with store.engine.begin() as conn:
            conn.execute(delete(inspections))
            conn.execute(delete(datasets))
            conn.execute(text('DELETE FROM entity_summaries'))
            conn.execute(text('DELETE FROM inspection_analytics'))
            conn.execute(text('DELETE FROM retrieval_versions'))
            conn.execute(text('DELETE FROM staging.inspection_source'))
            conn.execute(text('DELETE FROM staging.citation_source'))
            conn.execute(text('DELETE FROM staging.annual_source'))
            conn.execute(text('DELETE FROM staging.annual_metadata'))
            load_inspections(conn, expected_inspections)
            load_source_rows(conn, expected_inspection_rows, expected_citations)
            annual_count = load_annual_rows(conn, expected_annual)
            if conn.execute(select(text('count(*)')).select_from(inspections)).scalar_one() != expected_inspections:
                raise ValueError('PostgreSQL canonical inspection reconciliation failed.')
            imported_quality = dict(quality)
            imported_quality['imported_to'] = 'PostgreSQL'
            conn.execute(datasets.insert().values(id=1, payload=imported_quality))
        print(f'Committed {expected_inspections:,} inspections, '
              f'{expected_inspection_rows:,} inspection source rows, '
              f'{expected_citations:,} citation rows and {annual_count:,} annual rows.', flush=True)
    else:
        with store.engine.begin() as conn:
            source_counts = (
                conn.execute(text('SELECT count(*) FROM staging.inspection_source')).scalar_one(),
                conn.execute(text('SELECT count(*) FROM staging.citation_source')).scalar_one(),
                conn.execute(text('SELECT count(*) FROM staging.annual_source')).scalar_one(),
            )
            expected_counts = (expected_inspection_rows, expected_citations, expected_annual)
            metadata_id = conn.execute(text(
                'SELECT dataset_id FROM staging.annual_metadata WHERE id=1'
            )).scalar_one_or_none()
            if source_counts != expected_counts or metadata_id != quality['dataset_id']:
                conn.execute(text('DELETE FROM staging.inspection_source'))
                conn.execute(text('DELETE FROM staging.citation_source'))
                conn.execute(text('DELETE FROM staging.annual_source'))
                conn.execute(text('DELETE FROM staging.annual_metadata'))
                load_source_rows(conn, expected_inspection_rows, expected_citations)
                load_annual_rows(conn, expected_annual)

    from backend.services.mart import build
    from backend.database.retrieval_mart import prepare
    build(store)
    prepare(store)
    print('Real PostgreSQL dataset and analytics projections are ready.', flush=True)


if __name__ == '__main__':
    import_data()

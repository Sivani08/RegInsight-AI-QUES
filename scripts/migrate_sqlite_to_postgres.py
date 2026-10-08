"""One-time read-only import of historical databases. Never used by the application."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from psycopg import sql
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.database.postgres import connection

TABLES={
    'inspections':('public',['inspections','dataset','evidence','entity_summaries','inspection_analytics','retrieval_versions','dashboard_scope_sites','dashboard_scope_runs']),
    'intelligence':('intelligence',['texts','identities','observations','origins','conflicts','corpus','cache','runs','assignments','members','embeddings','quarantine','website_index_runs','website_index','website_reviews','retrieval_summaries']),
    'observations':('observation_workspace',['runs','tags','reviews']),
    'qc':('quality_control',['datasets','records','audit']),
    'knowledge':('knowledge',['sources','chunks']),
    'staging':('staging',['inspection_source','citation_source','annual_source']),
}


def migrate(source,kind):
    schema,tables=TABLES[kind]
    report=[]
    source=Path(source).resolve()
    # URI read-only mode prevents accidental journal/data changes in the original.
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as original, connection(schema) as target:
        target.execute("SET LOCAL statement_timeout='30min'")
        present={row[0] for row in original.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        for table in tables:
            if table not in present:
                continue
            count=original.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]
            existing=target.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
            if existing:
                raise ValueError(f'Target {schema}.{table} is not empty; use a clean migrated database for import and reconciliation')
            cursor=original.execute('SELECT * FROM "'+table+'"')
            columns=[item[0] for item in cursor.description]
            available={row[0] for row in target.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',(schema,table))}
            if not set(columns)<=available:
                raise ValueError(f'Unmapped columns in {table}: {set(columns)-available}')
            statement=sql.SQL('INSERT INTO {} ({}) OVERRIDING SYSTEM VALUE VALUES ({})').format(
                sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns))
            imported=0
            while batch:=cursor.fetchmany(1000):
                target.cursor().executemany(statement,batch)
                imported+=len(batch)
            actual=target.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
            if actual!=count or imported!=count:
                raise ValueError(f'Reconciliation mismatch in {table}; transaction rolled back')
            report.append({'source_table':table,'source_count':count,'postgres_table':schema+'.'+table,
                           'postgres_count':actual,'match':True,'error_count':0})
            if table in ('conflicts','quarantine'):
                target.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,'id'),GREATEST(coalesce(max(id),1),1),count(*)>0) FROM {}").format(sql.Identifier(table)),(schema+'.'+table,))
    return {'source':str(source),'kind':kind,'committed':True,'tables':report}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--kind',choices=TABLES,required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    report=migrate(args.source,args.kind)
    Path(args.report).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Imported and reconciled',len(report['tables']),'tables. Original source retained.')


if __name__=='__main__':
    main()

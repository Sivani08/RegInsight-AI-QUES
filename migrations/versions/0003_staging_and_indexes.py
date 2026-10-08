"""Source staging and browsing indexes in the authoritative database."""
from alembic import op
revision='0003_staging_and_indexes'
down_revision='0002_workflow_storage'
branch_labels=None
depends_on=None

def upgrade():
    op.get_bind().exec_driver_sql('''
    CREATE SCHEMA staging;
    CREATE TABLE staging.inspection_source (source_row INT,id TEXT,fei TEXT,company TEXT,city TEXT,state TEXT,country TEXT,fy INT,date TEXT,classification TEXT,posted TEXT,project TEXT,product TEXT,raw TEXT);
    CREATE TABLE staging.citation_source (source_row INT,id TEXT,fei TEXT,company TEXT,date TEXT,program TEXT,reference TEXT,short TEXT,long TEXT);
    CREATE TABLE staging.annual_source (year INT,sheet TEXT,source_row INT,program TEXT,cite_id TEXT,reference TEXT,short TEXT,long TEXT,frequency INT);
    CREATE INDEX staging_inspection_id ON staging.inspection_source(id);
    CREATE INDEX staging_citation_id ON staging.citation_source(id);
    CREATE INDEX retrieval_observation_date ON intelligence.website_index(run_id,dataset,grain,year DESC,id);
    CREATE INDEX retrieval_observation_theme ON intelligence.website_index(run_id,dataset,grain,theme,inspection_id);
    CREATE INDEX retrieval_observation_company ON intelligence.website_index(run_id,dataset,grain,company,id);
    CREATE INDEX retrieval_observation_site ON intelligence.website_index(run_id,dataset,grain,site,id);
    ''')

def downgrade():
    raise RuntimeError('Source staging may contain original evidence. Restore a verified backup for rollback.')

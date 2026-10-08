"""Keep annual benchmark source summaries in PostgreSQL."""
from alembic import op

revision = '0004_annual_benchmark_metadata'
down_revision = '0003_staging_and_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql('''
    CREATE TABLE staging.annual_metadata (
        id SMALLINT PRIMARY KEY CHECK (id = 1),
        dataset_id TEXT NOT NULL,
        payload JSONB NOT NULL
    )
    ''')


def downgrade():
    raise RuntimeError('Annual benchmark source provenance is retained; restore a verified backup for rollback.')

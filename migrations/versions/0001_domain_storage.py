"""Move the existing domain tables into one PostgreSQL database."""
from pathlib import Path
from alembic import op

revision = '0001_domain_storage'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Existing SQLAlchemy definitions preserve inspection JSON and deterministic queries.
    from backend.database.store import metadata
    import backend.database.retrieval_mart
    import backend.services.mart
    import backend.analytics.dashboard_queries
    metadata.create_all(op.get_bind())
    source = Path(__file__).parents[1] / 'domain_storage.sql'
    op.get_bind().exec_driver_sql(source.read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('This migration contains regulatory records. Restore a verified backup rather than dropping domain tables.')

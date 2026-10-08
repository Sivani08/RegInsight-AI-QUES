"""Durable, owner-scoped conversations and administrator evidence views."""
from pathlib import Path

from alembic import op

revision = '0005_chat_history'
down_revision = '0004_annual_benchmark_metadata'
branch_labels = None
depends_on = None


def upgrade():
    source = Path(__file__).resolve().parents[1] / 'chat_history.sql'
    op.get_bind().exec_driver_sql(source.read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('Chat audit history must be retained; restore a verified backup for rollback.')

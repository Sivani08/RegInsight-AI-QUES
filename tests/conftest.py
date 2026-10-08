"""Destructive fixture isolation is allowed only in a disposable test database."""
import os
import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(autouse=True)
def isolated_domain_tables(request):
    value=os.getenv('DATABASE_URL','')
    if not value:
        return
    name=make_url(value).database or ''
    if not name.startswith('reginsight_test_'):
        pytest.fail('Legacy regression fixtures require an isolated reginsight_test_ database')
    from backend.database.postgres import connection
    from psycopg import sql
    with connection() as current:
        rows=current.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','intelligence','observation_workspace','quality_control','knowledge','staging') AND tablename NOT IN ('alembic_version','embedding_metadata','retrieval_documents','retrieval_chunks','checkpoint_migrations') AND tablename NOT LIKE 'checkpoint%%'").fetchall()
        if rows:
            current.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(sql.SQL(',').join(sql.Identifier(row['schemaname'],row['tablename']) for row in rows)))
    from backend.cache.redis_cache import get_cache
    get_cache.cache_clear()

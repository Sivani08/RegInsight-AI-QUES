"""PostgreSQL connection boundaries shared by application repositories."""
import os
from contextlib import contextmanager
from functools import lru_cache
from collections.abc import Iterator

from psycopg import Connection, sql
from psycopg_pool import ConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

SCHEMAS = {'public', 'intelligence', 'observation_workspace', 'quality_control', 'knowledge', 'staging'}


def database_url() -> str:
    value = os.environ.get('DATABASE_URL', '')
    if not value:
        raise RuntimeError('DATABASE_URL is required. Run database migrations before starting the application.')
    parsed = make_url(value)
    if parsed.get_backend_name() != 'postgresql':
        raise RuntimeError('RegInsight requires PostgreSQL; no alternate database backend is supported.')
    return value


class DatabaseRow(dict):
    """Preserve existing domain readers that use column names or positions."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def domain_rows(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: DatabaseRow(zip(names, values))


@lru_cache(maxsize=1)
def connection_pool() -> ConnectionPool:
    url = make_url(database_url()).set(drivername='postgresql')
    return ConnectionPool(url.render_as_string(hide_password=False), min_size=1,
        max_size=int(os.getenv('DATABASE_POOL_SIZE', '10')), timeout=10,
        kwargs={'row_factory': domain_rows, 'connect_timeout': 5}, open=True)


@lru_cache(maxsize=1)
def application_engine():
    url = make_url(database_url()).set(drivername='postgresql+psycopg')
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5,
                         connect_args={'connect_timeout': 5})


@contextmanager
def connection(schema: str = 'public') -> Iterator[Connection]:
    if schema not in SCHEMAS:
        raise ValueError('Unknown application schema')
    with connection_pool().connection() as current:
        with current.transaction():
            current.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(schema)))
            current.execute("SET LOCAL statement_timeout = '30s'")
            yield current

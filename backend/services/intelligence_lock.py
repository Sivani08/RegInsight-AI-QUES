"""Database advisory lock coordinates tagging across API and worker processes."""
from contextlib import contextmanager
from backend.database.postgres import connection


@contextmanager
def run_lock(database):
    with connection('intelligence') as current:
        acquired = current.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))',
                                   ('observation-classification',)).fetchone()[0]
        if not acquired:
            raise ValueError('A tagging run is already active for this corpus')
        yield

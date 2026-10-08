"""Lease fencing and idempotency against an isolated migrated PostgreSQL database."""
import os
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from backend.database.postgres import connection
from backend.workflows import jobs
from backend.workflows.repository import Conflict

pytestmark=pytest.mark.skipif(not os.getenv('DATABASE_URL','').startswith('postgresql'),reason='Requires isolated migrated PostgreSQL')


@pytest.fixture
def owner():
    identifier=str(uuid.uuid4())
    with connection() as current:
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',(identifier,'Queue test','analyst',identifier))
    yield identifier
    with connection() as current:
        current.execute('DELETE FROM background_jobs WHERE user_id=%s',(identifier,))
        current.execute('DELETE FROM users WHERE id=%s',(identifier,))


def enqueue(owner,payload=None,key=None):
    with connection() as current:
        return jobs.enqueue(current,owner,None,payload or {},key or str(uuid.uuid4()),'index_references')


def test_idempotency_rejects_changed_request(owner):
    key=str(uuid.uuid4())
    first=enqueue(owner,{'test':1},key)
    assert enqueue(owner,{'test':1},key)==first
    with pytest.raises(Conflict):
        enqueue(owner,{'test':2},key)


def test_concurrent_claim_and_stale_lease_fencing(owner):
    identifier=enqueue(owner)
    with ThreadPoolExecutor(max_workers=2) as executor:
        claims=list(executor.map(lambda _:jobs.claim(),range(2)))
    claimed=[job for job in claims if job and job['id']==identifier]
    assert len(claimed)==1
    original=claimed[0]
    with connection() as current:
        current.execute("UPDATE background_jobs SET leased_until=now()-interval '1 second' WHERE id=%s",(identifier,))
    recovered=jobs.claim()
    assert recovered['id']==identifier
    assert recovered['attempts']==2
    assert not jobs.heartbeat(original)
    assert not jobs.finish(original)
    assert jobs.finish(recovered)


def test_retry_limit(owner):
    identifier=enqueue(owner)
    for attempt in range(1,4):
        job=jobs.claim()
        assert job['id']==identifier and job['attempts']==attempt
        jobs.finish(job,'NetworkError',retryable=True)
        with connection() as current:
            row=current.execute('SELECT status FROM background_jobs WHERE id=%s',(identifier,)).fetchone()
            assert row['status']==('FAILED' if attempt==3 else 'RETRYING')
            current.execute('UPDATE background_jobs SET available_at=now() WHERE id=%s',(identifier,))
    assert jobs.claim() is None

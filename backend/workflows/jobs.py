"""PostgreSQL queue with atomic claims, expiring leases and bounded retries."""
import uuid
from psycopg.types.json import Jsonb
from backend.database.postgres import connection


def enqueue(current, user_id, workflow_id, payload, key, job_type='workflow'):
    identifier=str(uuid.uuid4())
    row=current.execute('''INSERT INTO background_jobs(id,user_id,workflow_id,payload,idempotency_key,job_type)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(idempotency_key) DO UPDATE
        SET idempotency_key=EXCLUDED.idempotency_key RETURNING id,user_id,workflow_id,payload,job_type''',
        (identifier,user_id,workflow_id,Jsonb(payload),key,job_type)).fetchone()
    if (row['user_id'],row['workflow_id'],row['payload'],row['job_type']) != (user_id,workflow_id,payload,job_type):
        from .repository import Conflict
        raise Conflict('Idempotency key already belongs to a different job request')
    return row[0]


def fail_workflow(current, identifier, error):
    if not identifier:
        return
    from .repository import WorkflowRepository
    repository=WorkflowRepository()
    state=repository.get(identifier,current=current,lock=True)
    if state.status in ('COMPLETED','FAILED','REJECTED','AWAITING_HUMAN_REVIEW'):
        return
    state.status='FAILED'
    state.error=error
    state.final_response=None
    repository.save(state,'job_failed',{'error':error},current=current)


def claim():
    with connection() as current:
        expired=current.execute("""UPDATE background_jobs SET status='FAILED',error='Worker lease expired; attempt limit reached',finished_at=now()
            WHERE status='RUNNING' AND leased_until<now() AND attempts>=max_attempts RETURNING workflow_id""").fetchall()
        for item in expired:
            fail_workflow(current,item['workflow_id'],'Worker lease expired; attempt limit reached')
        row=current.execute("""SELECT * FROM background_jobs WHERE attempts<max_attempts AND
            ((status IN ('QUEUED','RETRYING') AND available_at<=now()) OR (status='RUNNING' AND leased_until<now()))
            ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not row:
            return None
        token=str(uuid.uuid4())
        current.execute("""UPDATE background_jobs SET status='RUNNING',attempts=attempts+1,
            lease_token=%s,leased_until=now()+interval '90 seconds',started_at=coalesce(started_at,now()) WHERE id=%s""", (token,row['id']))
        return {**row,'lease_token':token,'attempts':row['attempts']+1}


def heartbeat(job):
    with connection() as current:
        return current.execute("UPDATE background_jobs SET leased_until=now()+interval '90 seconds' WHERE id=%s AND lease_token=%s AND status='RUNNING'",(job['id'],job['lease_token'])).rowcount==1


def finish(job, error=None, retryable=False):
    retry=bool(error and retryable and job['attempts']<job['max_attempts'])
    status='RETRYING' if retry else 'FAILED' if error else 'COMPLETED'
    with connection() as current:
        changed=current.execute('''UPDATE background_jobs SET status=%s,error=%s,leased_until=NULL,
            finished_at=CASE WHEN %s THEN NULL ELSE now() END,available_at=now()+make_interval(secs=>%s)
            WHERE id=%s AND lease_token=%s AND status='RUNNING' ''',
            (status,error,retry,min(60,2**job['attempts']),job['id'],job['lease_token'])).rowcount
        if changed and status=='FAILED':
            fail_workflow(current,job['workflow_id'],error)
        return bool(changed)

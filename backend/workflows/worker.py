"""One recoverable local worker; deploy additional workers when capacity allows."""
import logging
import threading
import time
import httpx
import psycopg
from backend.database.store import Store
from backend.services.intelligence import Intelligence
from .factory import create_workflows
from . import jobs

log=logging.getLogger(__name__)


def perform_job(service,job):
    if job['job_type']=='workflow':
        return service.run(job['workflow_id'],job['payload'] or None)
    if job['job_type']=='index_references':
        from .policy import ROOT
        return service.retrieval.seed_references(ROOT)
    if job['job_type']=='index_document':
        return service.retrieval.ingest(job['payload'])
    if job['job_type']=='classification':
        from backend.services.observation_intelligence import run
        from backend.database.postgres import connection
        result=run(**job['payload'])
        with connection() as current:
            current.execute('UPDATE background_jobs SET result_reference=%s WHERE id=%s AND lease_token=%s',
                (result['id'],job['id'],job['lease_token']))
        return result
    raise ValueError('Unsupported job type')


def run_once(service):
    job=jobs.claim()
    if not job:
        return False
    stop=threading.Event()
    def renew():
        while not stop.wait(20):
            try:
                if not jobs.heartbeat(job):
                    return
            except psycopg.Error:
                log.warning('job_heartbeat_failed job_id=%s',job['id'])
    thread=threading.Thread(target=renew,daemon=True)
    thread.start()
    try:
        perform_job(service,job)
        jobs.finish(job)
    except (httpx.TimeoutException,httpx.NetworkError,psycopg.OperationalError) as error:
        jobs.finish(job,type(error).__name__,retryable=True)
    except Exception as error:
        jobs.finish(job,type(error).__name__,retryable=False)
        log.error('job_failed job_id=%s error_type=%s',job['id'],type(error).__name__)
    finally:
        stop.set()
        thread.join(timeout=2)
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    service=create_workflows(Intelligence(Store()))
    from backend.services.chat_history import expire_interrupted_turns
    last_recovery = 0
    while True:
        if time.monotonic() - last_recovery >= 60:
            expire_interrupted_turns()
            last_recovery = time.monotonic()
        if not run_once(service):
            time.sleep(1)


if __name__=='__main__':
    main()

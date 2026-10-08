"""Read-only local diagnostic counts and active query wait states."""
from backend.database.postgres import connection
with connection() as current:
    print('workflows',current.execute('SELECT count(*) FROM workflow_runs').fetchone()[0],flush=True)
    for row in current.execute("SELECT pid,state,wait_event_type,wait_event,left(query,90) query FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"):
        print(dict(row),flush=True)

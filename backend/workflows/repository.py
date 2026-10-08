"""Atomic workflow revisions and event history in PostgreSQL."""
from contextlib import nullcontext
from psycopg.types.json import Jsonb
from backend.database.postgres import connection
from .schemas import WorkflowState, now


class Conflict(ValueError):
    pass


class WorkflowRepository:
    def create(self, state, current=None):
        with nullcontext(current) if current is not None else connection() as current:
            current.execute('''INSERT INTO workflow_runs(id,user_id,session_id,status,revision,payload)
                VALUES (%s,%s,%s,%s,%s,%s)''', (state.workflow_id,state.user_id,state.session_id,state.status,state.revision,Jsonb(state.model_dump(mode='json'))))
            current.execute('INSERT INTO workflow_events(workflow_id,sequence,event,payload) VALUES (%s,0,%s,%s)', (state.workflow_id,'received',Jsonb({})))

    def get(self, identifier, current=None, lock=False):
        with nullcontext(current) if current is not None else connection() as current:
            row=current.execute('SELECT payload FROM workflow_runs WHERE id=%s'+(' FOR UPDATE' if lock else ''), (identifier,)).fetchone()
        if row is None:
            raise KeyError('Workflow not found')
        return WorkflowState.model_validate(row[0])

    def save(self, state, event, detail=None, current=None):
        previous=state.revision
        saved=state.model_copy(deep=True)
        saved.revision+=1
        saved.updated_at=now()
        with nullcontext(current) if current is not None else connection() as current:
            changed=current.execute('''UPDATE workflow_runs SET status=%s,revision=%s,payload=%s,updated_at=now()
                WHERE id=%s AND revision=%s''', (saved.status,saved.revision,Jsonb(saved.model_dump(mode='json')),saved.workflow_id,previous)).rowcount
            if changed!=1:
                raise Conflict('Workflow changed; reload before retrying')
            current.execute('INSERT INTO workflow_events(workflow_id,sequence,event,payload) VALUES (%s,%s,%s,%s)',
                (saved.workflow_id,saved.revision,event,Jsonb({'status':saved.status,**(detail or {})})))
        return saved

    def pending(self, principal):
        with connection() as current:
            rows=current.execute("SELECT payload FROM workflow_runs WHERE status='AWAITING_HUMAN_REVIEW' AND (%s OR user_id=%s) ORDER BY created_at DESC LIMIT 100", (principal.role in ('reviewer','admin'),principal.user_id)).fetchall()
        return [WorkflowState.model_validate(row[0]) for row in rows]

    def events(self, identifier):
        with connection() as current:
            rows=current.execute('SELECT sequence,event,payload,created_at FROM workflow_events WHERE workflow_id=%s ORDER BY sequence', (identifier,)).fetchall()
        return [{'sequence':row['sequence'],'event':row['event'],**row['payload'],'timestamp':row['created_at'].isoformat()} for row in rows]

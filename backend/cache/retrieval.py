"""Versioned analytical caches. Conversation IDs and authentication are never cached."""
from functools import wraps
from inspect import signature
from pathlib import Path
from backend.cache.redis_cache import get_cache

def inspection_identity(service):
    info=service.info()
    return [str(service.store.engine.url),id(service.store.engine),info['dataset_id'],info.get('as_of'),service.config]

def workspace_cache(fn):
    sig=signature(fn)
    @wraps(fn)
    def wrapped(*args,**kwargs):
        from backend.api import workspace
        bound=sig.bind(*args,**kwargs);bound.apply_defaults()
        values=dict(bound.arguments)
        # FastAPI resolves Query defaults; direct Python callers may not.
        from fastapi.params import Param
        values={k:(v.default if isinstance(v,Param) else v) for k,v in values.items()}
        rid=values.get('run_id') or workspace.intelligence.latest(workspace.DB)['id']
        with workspace.db(workspace.DB) as c:
            workspace.review_table(c)
            revision=c.execute('SELECT coalesce(max(storage_sequence),0) FROM website_reviews WHERE run_id=%s',(rid,)).fetchone()[0]
        cache=get_cache()
        key=cache.key('workspace-'+fn.__name__,[str(Path(workspace.DB).resolve()),rid,revision,values])
        # Pin the snapshot used by the factory to the identity resolved above.
        if 'run_id' in sig.parameters:values['run_id']=rid
        return cache.remember(key,lambda:fn(**values),ttl=60)
    return wrapped

"""Cache only completed immutable observation runs, with typed reads."""
from functools import wraps
from inspect import signature
from pathlib import Path
from backend.cache.redis_cache import get_cache

def snapshot_cache(model):
    def decorate(fn):
        sig=signature(fn)
        @wraps(fn)
        def wrapped(*args,**kwargs):
            from backend.services.observation_intelligence import latest,db
            cache=get_cache()
            if not cache.available():return fn(*args,**kwargs)
            bound=sig.bind(*args,**kwargs);bound.apply_defaults();values=dict(bound.arguments)
            filters=values.pop('filters',{})
            rid=filters.get('run_id')
            path=values['path']
            if rid:
                import json
                with db(path) as c:
                    row=c.execute('SELECT payload FROM runs WHERE id=%s',(rid,)).fetchone()
                if not row or json.loads(row[0]).get('status')!='completed':return fn(*args,**kwargs)
            else:rid=latest(path)['id']
            filters={**filters,'run_id':rid};values['path']=str(Path(path).resolve())
            key=cache.key(fn.__name__,{'arguments':values,'filters':filters})
            value=cache.get(key)
            if value is not None:
                try:
                    result=model.model_validate(value)
                    if result.run_id!=rid:raise ValueError('Run mismatch')
                    for r in getattr(result,'records',[]):r.tag.verify_evidence(r.observation_text)
                    return result
                except ValueError:cache.bump('invalid')
            result=fn(**{**{k:v for k,v in bound.arguments.items() if k!='filters'},**filters})
            cache.put(key,result.model_dump())
            return result
        return wrapped
    return decorate

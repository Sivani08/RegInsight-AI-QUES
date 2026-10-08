"""Optional Redis acceleration; durable data always remains in the database."""
import hashlib,json,logging,os,time
from functools import lru_cache
from threading import Lock, Event
from collections import OrderedDict
from copy import deepcopy

class RedisCache:
    def __init__(self,client=None,enabled=None,clock=time.monotonic):
        self.enabled=os.getenv('REDIS_ENABLED','false').lower()=='true' if enabled is None else enabled
        self.client=client;self.clock=clock;self.retry_at=0.;self.lock=Lock()
        self.ttl=max(1,int(os.getenv('REDIS_CACHE_TTL_SECONDS','300')))
        self.max_bytes=max(1,int(os.getenv('REDIS_MAX_VALUE_BYTES','2000000')))
        self.namespace=os.getenv('REDIS_NAMESPACE','inspection-insights')
        self.stats={'hits':0,'misses':0,'errors':0,'writes':0,'invalid':0,'oversize':0}
        self.local=OrderedDict();self.pending={};self.local_bytes=0
        self.local_limit=32*1024*1024;self.local_entries=128
        self.local_stats={'hits':0,'misses':0,'coalesced':0}
        if self.enabled and client is None:
            try:
                import redis
                from redis.backoff import NoBackoff
                from redis.retry import Retry
                timeout=float(os.getenv('REDIS_TIMEOUT_SECONDS','0.25'))
                self.client=redis.Redis.from_url(os.getenv('REDIS_URL','redis://127.0.0.1:6379/0'),socket_connect_timeout=timeout,socket_timeout=timeout,decode_responses=True,retry=Retry(NoBackoff(),0),max_connections=20)
            except (ImportError,ValueError):self.client=None
    def key(self,kind,identity):
        digest=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
        return f'{self.namespace}:v1:{kind}:{digest}'
    def available(self):return self.enabled and self.client is not None and self.clock()>=self.retry_at
    def bump(self,name):
        with self.lock:self.stats[name]+=1
    def failure(self):
        self.bump('errors');self.retry_at=self.clock()+30
        logging.getLogger(__name__).warning('Redis unavailable; serving from the database')
    def get(self,key):
        if not self.available():return None
        try:
            raw=self.client.get(key)
            if raw is None:self.bump('misses');return None
            if len(raw.encode('utf-8'))>self.max_bytes:self.bump('oversize');return None
            value=json.loads(raw);self.bump('hits');return value
        except (ValueError,UnicodeError):self.bump('invalid');return None
        except Exception:self.failure();return None
    def put(self,key,value,ttl=None):
        if not self.available():return
        try:raw=json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        except (ValueError,TypeError):self.bump('invalid');return
        if len(raw.encode('utf-8'))>self.max_bytes:self.bump('oversize');return
        try:self.client.set(key,raw,ex=ttl or self.ttl);self.bump('writes')
        except Exception:self.failure()
    def remember(self,key,factory,ttl=300):
        """Bounded L1 with single-flight computation. Failures are never cached."""
        while True:
            with self.lock:
                item=self.local.get(key)
                if item and item[0]>self.clock():
                    self.local.move_to_end(key);self.local_stats['hits']+=1
                    return deepcopy(item[1])
                if item:
                    self.local_bytes-=self.local.pop(key)[2]
                event=self.pending.get(key)
                if event is None:
                    event=Event();self.pending[key]=event;self.local_stats['misses']+=1
                    break
                self.local_stats['coalesced']+=1
            event.wait()
        try:
            value=factory()
            size=len(json.dumps(value,default=str).encode('utf-8'))
            if size<=self.max_bytes:
                with self.lock:
                    while self.local and (len(self.local)>=self.local_entries or self.local_bytes+size>self.local_limit):
                        self.local_bytes-=self.local.popitem(last=False)[1][2]
                    self.local[key]=(self.clock()+ttl,deepcopy(value),size);self.local_bytes+=size
            return value
        finally:
            with self.lock:self.pending.pop(key,None);event.set()

    def status(self):
        state='disabled' if not self.enabled else 'unavailable'
        if self.available():
            try:
                if self.client.ping():state='connected'
            except Exception:self.failure()
        with self.lock:stats=dict(self.stats)
        return {'enabled':self.enabled,'status':state,'ttl_seconds':self.ttl,'counters':stats,'scope':'this application worker','fallback':'database',
                'local':{**self.local_stats,'entries':len(self.local),'bytes':self.local_bytes,'max_bytes':self.local_limit}}
    def close(self):
        if self.client is not None:
            try:self.client.close()
            except Exception:pass

@lru_cache(maxsize=1)
def get_cache():return RedisCache()

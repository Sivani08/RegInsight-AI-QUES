"""Shared outbound request budget. Includes retries; no credentials in logs."""
import os,time,json,math,threading
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone
import httpx
class RequestLimit(ValueError):pass
class RequestGate:
    def __init__(self,enabled=None,max_requests=None,rate=None,sleep=time.sleep,clock=time.monotonic):
        self.enabled=(os.getenv('AI_ENABLE_REMOTE','false').lower()=='true') if enabled is None else enabled
        self.maximum=int(os.getenv('AI_MAX_REQUESTS') or os.getenv('AI_MAX_REQUESTS_PER_RUN','20')) if max_requests is None else max_requests
        self.rate=float(os.getenv('AI_RATE_LIMIT','5')) if rate is None else rate
        if self.maximum<0 or self.rate<=0:raise ValueError('Invalid AI limits')
        self.sleep=sleep;self.clock=clock;self.last=None;self.requests=0;self.disabled=False;self.local_disabled=False;self.failures=0
        self.lock=threading.RLock()
        self.token_limit=int(os.getenv('AI_TOKEN_LIMIT_PER_MINUTE','20000'));self.window=self.clock();self.estimated_tokens=0
    def acquire(self,local=False):
        with self.lock:return self._acquire(local)
    def _acquire(self,local=False):
        if (not self.enabled and not local) or (self.local_disabled if local else self.disabled):raise RequestLimit('Remote disabled or provider circuit open')
        if self.requests>=self.maximum:raise RequestLimit('Request budget exhausted')
        if self.last is not None:self.sleep(max(0,60/self.rate-(self.clock()-self.last)))
        self.requests+=1;self.last=self.clock()
    def request(self,url,payload,headers,timeout,local=False):
        # Serialize outbound work and all budget/token accounting, including retries.
        with self.lock:return self._request(url,payload,headers,timeout,local)
    def open_circuit(self,local):
        if local:self.local_disabled=True
        else:self.disabled=True
    def _request(self,url,payload,headers,timeout,local=False):
        estimated=math.ceil(len(json.dumps(payload).encode('utf-8'))/3)+1500
        if estimated>self.token_limit:raise RequestLimit('Estimated token request exceeds configured per-minute budget')
        for attempt in range(3):
            if self.clock()-self.window>=60:self.window=self.clock();self.estimated_tokens=0
            if self.estimated_tokens+estimated>self.token_limit:
                self.sleep(max(0,60-(self.clock()-self.window)));self.window=self.clock();self.estimated_tokens=0
            self.acquire(local)
            self.estimated_tokens+=estimated
            try:
                with httpx.Client(timeout=timeout) as client:
                    response=client.post(url,json=payload,headers=headers)
                response.raise_for_status();return response.json()
            except (httpx.TimeoutException,httpx.TransportError):
                self.failures+=1
                if attempt==2:self.open_circuit(local);raise
                self.sleep(2**attempt)
            except httpx.HTTPStatusError as e:
                self.failures+=1
                status=e.response.status_code
                if status not in (429,500,502,503,504) or attempt==2:
                    self.open_circuit(local);raise
                value=e.response.headers.get('retry-after','')
                try:delay=float(value)
                except ValueError:
                    try:delay=(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()
                    except Exception:delay=2**attempt
                if delay>60:self.open_circuit(local);raise RequestLimit('Long provider cooldown; retry in a later run') from None
                self.sleep(max(2**attempt,delay))

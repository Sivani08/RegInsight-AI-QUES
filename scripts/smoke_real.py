import json,time,urllib.request
base='http://127.0.0.1:8017'
def req(path,body=None):
 t=time.perf_counter();r=urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'}),timeout=180);data=json.load(r);print(path,round(time.perf_counter()-t,2),str(data)[:400],flush=True);return data
req('/api/dashboard')
a=req('/api/agent/dashboard-query',{'question':'Which sites have the highest risk?','limit':3})
b=req('/api/agent/dashboard-query',{'question':'Why is the first one high?','context':a['context']})
req('/api/agent/dashboard-query',{'question':'What stands out?','focus':'observation_intelligence','limit':3})
req('/api/workspace/observations?dataset=real&limit=1')

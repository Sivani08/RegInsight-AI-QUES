// Memory only: exact URL keys, bounded size, short TTL, no authentication caching.
const completed=new Map(), pending=new Map();
let epoch=0, bytes=0;
export function clearRequestCache(){epoch++;completed.clear();pending.clear();bytes=0;}
export async function cachedRequest(path,body,signal,refresh=false){
  if(signal?.aborted)throw new DOMException('Aborted','AbortError');
  const mutation=body!=null, cacheable=!mutation&&!path.startsWith('/auth/')&&!path.startsWith('/cache/');
  if(mutation)clearRequestCache();
  const generation=epoch, key=epoch+':'+path;
  const hit=completed.get(key);
  if(cacheable&&!refresh&&hit&&hit.expires>Date.now())return structuredClone(hit.value);
  let job=cacheable&&!refresh?pending.get(key):null;
  if(!job){
    job=(async()=>{
      const response=await fetch('/api'+path,{
        signal:AbortSignal.timeout(120000),
        ...(mutation?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})
      });
      let value;
      try{value=await response.json();}catch{throw new Error('The data service is unavailable. Start the FastAPI service and retry.');}
      if(!response.ok){if(response.status===401)clearRequestCache();throw new Error(typeof value.detail==='string'?value.detail:'The request could not be completed. Check the supplied values.');}
      if(cacheable&&generation===epoch){
        const size=JSON.stringify(value).length*2;
        if(size<=2*1024*1024){
          if(completed.has(key)){bytes-=completed.get(key).size;completed.delete(key);}
          while(completed.size&&(completed.size>=32||bytes+size>8*1024*1024)){
            const first=completed.keys().next().value;bytes-=completed.get(first).size;completed.delete(first);
          }
          completed.set(key,{value,size,expires:Date.now()+15000});bytes+=size;
        }
      }
      return value;
    })();
    if(cacheable&&!refresh)pending.set(key,job);
    const cleanup=()=>{if(pending.get(key)===job)pending.delete(key);};
    job.then(cleanup,cleanup);
  }
  if(!signal)return structuredClone(await job);
  return new Promise((resolve,reject)=>{
    const abort=()=>reject(new DOMException('Aborted','AbortError'));
    signal.addEventListener('abort',abort,{once:true});
    job.then(value=>{if(!signal.aborted)resolve(structuredClone(value));},reject)
      .finally(()=>signal.removeEventListener('abort',abort));
  });
}

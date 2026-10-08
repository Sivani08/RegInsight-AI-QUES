import test from 'node:test';
import assert from 'node:assert/strict';
import {cachedRequest,clearRequestCache} from '../src/reginsight/request-cache.js';

test('deduplicates, isolates scopes, invalidates mutations and preserves callers',async()=>{
  clearRequestCache();let calls=0;
  globalThis.fetch=async url=>{calls++;await new Promise(r=>setTimeout(r,10));return {ok:true,json:async()=>({url,rows:[1]})};};
  const controller=new AbortController();
  const aborted=cachedRequest('/dashboard?year=2025',null,controller.signal);
  const active=cachedRequest('/dashboard?year=2025');controller.abort();
  await assert.rejects(aborted,{name:'AbortError'});const value=await active;assert.equal(calls,1);
  value.rows.push(2);assert.deepEqual((await cachedRequest('/dashboard?year=2025')).rows,[1]);assert.equal(calls,1);
  assert.equal((await cachedRequest('/dashboard?year=2024')).url,'/api/dashboard?year=2024');assert.equal(calls,2);
  await cachedRequest('/workspace/reviews',{});await cachedRequest('/dashboard?year=2025');assert.equal(calls,4);
  await cachedRequest('/dashboard?year=2025',null,null,true);assert.equal(calls,5);
  await cachedRequest('/auth/status');await cachedRequest('/auth/status');assert.equal(calls,7);
});

test('an in-flight read cannot repopulate cache after a mutation',async()=>{
  clearRequestCache();let release,calls=0;
  globalThis.fetch=async(url,options)=>{calls++;if(!options.method&&calls===1)await new Promise(r=>release=r);return {ok:true,json:async()=>({calls})};};
  const old=cachedRequest('/dashboard');await cachedRequest('/auth/logout',{});release();await old;
  await cachedRequest('/dashboard');assert.equal(calls,3);
});

test('failed requests are not cached',async()=>{
  clearRequestCache();let calls=0;
  globalThis.fetch=async()=>{calls++;return {ok:false,status:503,json:async()=>({detail:'Unavailable'})};};
  await assert.rejects(cachedRequest('/dashboard'));await assert.rejects(cachedRequest('/dashboard'));assert.equal(calls,2);
});

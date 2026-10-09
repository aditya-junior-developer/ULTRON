import { afterEach, describe, expect, it, vi } from 'vitest';
import worker, { type Env } from './index';
const userId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const env:Env={SUPABASE_URL:'https://example.supabase.co',SUPABASE_ANON_KEY:'public-test-key',ALLOWED_ORIGIN:'https://ultron.example',GEMINI_MODEL:'',GEMINI_FREE_TIER_CONFIRMED:'false',MAX_DAILY_AI_REQUESTS:'20',ASSETS:{fetch:async()=>new Response('assets')} as unknown as Fetcher};
function request(path:string,method='GET',data?:unknown){return new Request('https://ultron.example'+path,{method,headers:{Authorization:'Bearer test-session','X-ULTRON-Device-Token':'test-device-token',...(data?{'Content-Type':'application/json'}:{})},body:data?JSON.stringify(data):undefined});}
afterEach(()=>vi.unstubAllGlobals());
describe('cloud boundaries',()=>{
 it('rejects missing or revoked device credentials',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:[])));
  const missing=await worker.fetch(new Request('https://ultron.example/status',{headers:{Authorization:'Bearer test-session'}}),env);
  expect(missing.status).toBe(401);
  const revoked=await worker.fetch(request('/status'),env);expect(revoked.status).toBe(403);
 });
 it('allows health without an account and denies protected access without a session',async()=>{
  expect((await worker.fetch(new Request('https://ultron.example/health'),env)).status).toBe(200);
  expect((await worker.fetch(new Request('https://ultron.example/tasks'),env)).status).toBe(401);
 });
 it('rejects unapproved web origins',async()=>{
  const r=await worker.fetch(new Request('https://ultron.example/tasks',{headers:{Origin:'https://attacker.example'}}),env);expect(r.status).toBe(403);
 });
 it('does not claim desktop capabilities in cloud mode',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[])));
  const status=await (await worker.fetch(request('/status'),env)).json() as any;
  expect(status.permissions.automation).toBe(false);expect(status.voice.running).toBe(false);expect(status.ai.ollama.models).toEqual([]);
 });
 it('rejects arbitrary cloud commands',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[])));
  const r=await worker.fetch(request('/tasks','POST',{action:'shell',args:{command:'evil'}}),env);expect(r.status).toBe(400);
 });
 it('scopes database queries to authenticated ownership',async()=>{
  const calls:string[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push(url);return Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[]);}));
  const r=await worker.fetch(request('/tasks'),env);expect(r.status).toBe(200);expect(calls[1]).toContain(`user_id=eq.${userId}`);
 });
 it('blocks cloud AI before provider requests if free access is unconfirmed',async()=>{
  const fetch=vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[]));vi.stubGlobal('fetch',fetch);
  const r=await worker.fetch(request('/chat','POST',{message:'hello'}),env);expect(r.status).toBe(409);expect(fetch).toHaveBeenCalledTimes(2);
 });
 it('denies cross-device desktop permissions',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[])));
  const r=await worker.fetch(request('/settings','PATCH',{screen:true}),env);expect(r.status).toBe(409);
 });
 it('requires explicit confirmation before cloud data deletion',async()=>{
  const fetch=vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[]));vi.stubGlobal('fetch',fetch);
  const r=await worker.fetch(request('/erase','POST',{approved:false}),env);expect(r.status).toBe(400);expect(fetch).toHaveBeenCalledTimes(2);
 });
 it('rejects foreign ownership supplied in sync records',async()=>{
  const fetch=vi.fn(async(url:string)=>Response.json(url.includes('/auth/')?{id:userId}:url.includes('token_hash=')?[{id:'registered'}]:[]));vi.stubGlobal('fetch',fetch);
  const r=await worker.fetch(request('/sync','POST',{conversations:[],messages:[],memories:[],user_id:'other'}),env);expect(r.status).toBe(400);
 });
});

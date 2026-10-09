import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';

test('migration executes; RLS separates owners and protects quotas and scheduler', async()=>{
 const db=new PGlite();
 try{
  await db.exec(`create schema auth; create role anon; create role authenticated; create role service_role bypassrls;
   create table auth.users(id uuid primary key);
   create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
   grant usage on schema auth to authenticated,service_role;
   grant execute on function auth.uid() to authenticated,service_role;
   insert into auth.users values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');`);
  await db.exec(await readFile(new URL('../supabase/migrations/001_initial.sql',import.meta.url),'utf8'));
  await db.exec(`set role authenticated; set request.jwt.claim.sub='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';`);
  await db.exec(`insert into public.memories values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111','User A private memory',1,1)`);
  await assert.rejects(db.exec(`insert into public.memories values ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','22222222-2222-4222-8222-222222222222','Foreign insert',1,1)`),/row-level security/);
  for(let i=0;i<2;i++)assert.equal((await db.query('select public.consume_ai_budget(2) as allowed')).rows[0].allowed,true);
  assert.equal((await db.query('select public.consume_ai_budget(2) as allowed')).rows[0].allowed,false);
  await assert.rejects(db.exec('delete from public.ai_daily_usage'),/permission denied/);
  await assert.rejects(db.query('select public.run_due_reminders()'),/permission denied/);
  await db.exec(`set request.jwt.claim.sub='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'`);
  assert.equal((await db.query('select * from public.memories')).rows.length,0);
  await db.exec(`insert into public.schedules values ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','33333333-3333-4333-8333-333333333333','reminder','{"message":"Cloud check"}',900,1,1)`);
  await db.exec('reset role; set role service_role');
  assert.equal((await db.query('select public.run_due_reminders() as count')).rows[0].count,1);
  assert.equal((await db.query('select public.run_due_reminders() as count')).rows[0].count,0);
  await db.exec(`reset role; set role authenticated; set request.jwt.claim.sub='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'`);
  assert.equal((await db.query('select * from public.activity_events')).rows[0].detail,'Cloud check');
 }finally{await db.close();}
});

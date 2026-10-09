-- REVIEW ONLY: applying this migration requires separate user approval.
begin;
create table public.profiles (id uuid primary key references auth.users(id) on delete cascade, display_name text, created_at timestamptz not null default now());
create table public.user_settings (user_id uuid primary key references auth.users(id) on delete cascade, retention_days integer not null default 30 check(retention_days between 1 and 3650));
create table public.devices (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, name text not null, platform text not null, last_seen double precision not null, token_hash text not null, revoked boolean not null default false, primary key(user_id,id));
create table public.conversations (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, title text not null, created double precision not null, primary key(user_id,id));
create table public.messages (user_id uuid not null, id uuid not null, conversation_id uuid not null, role text not null check(role in ('user','assistant')), content text not null check(length(content)<=20000), created double precision not null, primary key(user_id,id), foreign key(user_id,conversation_id) references public.conversations(user_id,id) on delete cascade);
create table public.memories (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, content text not null check(length(content)<=10000), created double precision not null, updated double precision not null, primary key(user_id,id));
create table public.tasks (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, action text not null check(action='reminder'), args jsonb not null, status text not null check(status in ('queued','running','completed','failed','canceled')), risk text not null default 'low' check(risk='low'), result jsonb, error text, expires double precision, created double precision not null, primary key(user_id,id));
create table public.schedules (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, action text not null check(action='reminder'), args jsonb not null, interval_seconds integer not null check(interval_seconds between 900 and 31536000), next_run double precision not null, enabled integer not null default 1 check(enabled in (0,1)), primary key(user_id,id));
create table public.activity_events (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, kind text not null, detail text not null, created double precision not null, primary key(user_id,id));
create table public.integration_connections (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, provider text not null, account_label text, scopes text[] not null default '{}', primary key(user_id,id));
create table public.approvals (user_id uuid not null references auth.users(id) on delete cascade, id uuid not null, action text not null, expires_at timestamptz not null, status text not null check(status in ('pending','approved','rejected','expired')), primary key(user_id,id));
create table public.sync_changes (user_id uuid not null references auth.users(id) on delete cascade, entity_id uuid not null, entity_type text not null check(entity_type in ('memories','conversations')), deleted double precision not null, primary key(user_id,entity_type,entity_id));
create table public.ai_daily_usage (user_id uuid not null references auth.users(id) on delete cascade, day date not null, requests integer not null default 0, primary key(user_id,day));
create index messages_conversation on public.messages(user_id,conversation_id,created);
create index due_schedules on public.schedules(next_run) where enabled=1;
do $$ declare t text; begin
 foreach t in array array['profiles','user_settings','devices','conversations','messages','memories','tasks','schedules','activity_events','integration_connections','approvals','sync_changes','ai_daily_usage'] loop
  execute format('alter table public.%I enable row level security',t);
  if t='profiles' then
   execute format('create policy owner on public.%I for all to authenticated using ((select auth.uid())=id) with check ((select auth.uid())=id)',t);
  elsif t='ai_daily_usage' then
   execute 'create policy usage_read on public.ai_daily_usage for select to authenticated using ((select auth.uid())=user_id)';
  else
   execute format('create policy owner on public.%I for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id)',t);
  end if;
 end loop;
end $$;
grant usage on schema public to authenticated,service_role;
grant select,insert,update,delete on all tables in schema public to authenticated,service_role;
revoke insert,update,delete on public.ai_daily_usage from authenticated;
-- Authenticated users cannot reset their quota counters. Security-definer function binds auth.uid().
create function public.consume_ai_budget(daily_limit integer) returns boolean language plpgsql security definer set search_path=public as $$
declare n integer; uid uuid := auth.uid(); begin
 if uid is null or daily_limit<1 or daily_limit>100 then return false; end if;
 insert into public.ai_daily_usage(user_id,day,requests) values(uid,current_date,1)
 on conflict(user_id,day) do update set requests=ai_daily_usage.requests+1 where ai_daily_usage.requests<daily_limit
 returning requests into n;
 return n is not null;
end $$;
revoke all on function public.consume_ai_budget(integer) from public,anon;
grant execute on function public.consume_ai_budget(integer) to authenticated;
create function public.run_due_reminders() returns integer language plpgsql security definer set search_path=public as $$
declare r record; count integer := 0; now_seconds double precision := extract(epoch from now()); begin
 for r in select * from public.schedules where enabled=1 and next_run<=now_seconds order by next_run for update skip locked limit 100 loop
  update public.schedules set next_run=now_seconds+r.interval_seconds where user_id=r.user_id and id=r.id;
  insert into public.tasks(user_id,id,action,args,status,risk,result,created) values(r.user_id,gen_random_uuid(),'reminder',r.args,'completed','low',r.args,now_seconds);
  insert into public.activity_events(user_id,id,kind,detail,created) values(r.user_id,gen_random_uuid(),'reminder',left(r.args->>'message',2000),now_seconds);
  count:=count+1;
 end loop;
 delete from public.ai_daily_usage where day<current_date-30;
 return count;
end $$;
revoke all on function public.run_due_reminders() from public,anon,authenticated;
grant execute on function public.run_due_reminders() to service_role;
commit;

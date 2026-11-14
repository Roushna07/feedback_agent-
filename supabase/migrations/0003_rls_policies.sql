-- =============================================================================
-- 0003_rls_policies.sql
-- Rural Healthcare Multilingual Feedback Agent — Supabase phase 1
--
-- Purpose : enable Row Level Security on every exposed table and apply
--           least-privilege grants.
-- Target  : Supabase SQL Editor (free tier). Safe to re-run (idempotent).
--
-- Access model
--   camp_staff : read/write ONLY rows whose camp_id = their authorized camp
--   admin      : read/write rows of their camp; if their camp_id IS NULL,
--                read/write rows of every camp
--   anon       : no access at all
--   delete     : admins only (the application never deletes patient data)
-- =============================================================================

alter table public.camps            enable row level security;
alter table public.profiles         enable row level security;
alter table public.feedback_sessions enable row level security;
alter table public.feedback_answers  enable row level security;

-- ---------------------------------------------------------------------------
-- camps
-- ---------------------------------------------------------------------------
drop policy if exists camps_select on public.camps;
create policy camps_select on public.camps
    for select to authenticated
    using (public.can_access_camp(id));

drop policy if exists camps_insert_admin on public.camps;
create policy camps_insert_admin on public.camps
    for insert to authenticated
    with check (public.is_admin());

drop policy if exists camps_update_admin on public.camps;
create policy camps_update_admin on public.camps
    for update to authenticated
    using (public.is_admin())
    with check (public.is_admin());

drop policy if exists camps_delete_admin on public.camps;
create policy camps_delete_admin on public.camps
    for delete to authenticated
    using (public.is_admin());

-- ---------------------------------------------------------------------------
-- profiles  (no recursion: is_admin()/my_camp_id() are SECURITY DEFINER)
-- ---------------------------------------------------------------------------
drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles
    for select to authenticated
    using (user_id = auth.uid() or public.is_admin());

drop policy if exists profiles_insert_admin on public.profiles;
create policy profiles_insert_admin on public.profiles
    for insert to authenticated
    with check (public.is_admin());

drop policy if exists profiles_update_admin on public.profiles;
create policy profiles_update_admin on public.profiles
    for update to authenticated
    using (public.is_admin())
    with check (public.is_admin());

-- no DELETE policy: profiles rows are managed by auth.users cascades only

-- ---------------------------------------------------------------------------
-- feedback_sessions
-- ---------------------------------------------------------------------------
drop policy if exists sessions_select on public.feedback_sessions;
create policy sessions_select on public.feedback_sessions
    for select to authenticated
    using (public.can_access_camp(camp_id));

drop policy if exists sessions_insert on public.feedback_sessions;
create policy sessions_insert on public.feedback_sessions
    for insert to authenticated
    with check (public.can_access_camp(camp_id));

drop policy if exists sessions_update on public.feedback_sessions;
create policy sessions_update on public.feedback_sessions
    for update to authenticated
    using (public.can_access_camp(camp_id))
    with check (public.can_access_camp(camp_id));

drop policy if exists sessions_delete_admin on public.feedback_sessions;
create policy sessions_delete_admin on public.feedback_sessions
    for delete to authenticated
    using (public.is_admin());

-- ---------------------------------------------------------------------------
-- feedback_answers (scope inherited from the parent session's camp)
-- ---------------------------------------------------------------------------
drop policy if exists answers_select on public.feedback_answers;
create policy answers_select on public.feedback_answers
    for select to authenticated
    using (exists (
        select 1 from public.feedback_sessions s
        where s.id = session_id
          and public.can_access_camp(s.camp_id)));

drop policy if exists answers_insert on public.feedback_answers;
create policy answers_insert on public.feedback_answers
    for insert to authenticated
    with check (exists (
        select 1 from public.feedback_sessions s
        where s.id = session_id
          and public.can_access_camp(s.camp_id)));

drop policy if exists answers_update on public.feedback_answers;
create policy answers_update on public.feedback_answers
    for update to authenticated
    using (exists (
        select 1 from public.feedback_sessions s
        where s.id = session_id
          and public.can_access_camp(s.camp_id)))
    with check (exists (
        select 1 from public.feedback_sessions s
        where s.id = session_id
          and public.can_access_camp(s.camp_id)));

drop policy if exists answers_delete_admin on public.feedback_answers;
create policy answers_delete_admin on public.feedback_answers
    for delete to authenticated
    using (public.is_admin());

-- ---------------------------------------------------------------------------
-- Least-privilege grants.
-- Supabase's default privileges hand full table access to anon+authenticated;
-- we tighten that: anon gets nothing, authenticated gets read/write only
-- (no DELETE, no TRUNCATE, no schema DDL).
-- ---------------------------------------------------------------------------
revoke all on all tables in schema public from anon;
revoke all on all tables in schema public from anon, authenticated;

grant usage on schema public to anon, authenticated;
grant select, insert, update on
    public.camps,
    public.profiles,
    public.feedback_sessions,
    public.feedback_answers
    to authenticated;
grant usage, select on all sequences in schema public to authenticated;

grant execute on function public.is_admin() to authenticated;
grant execute on function public.my_camp_id() to authenticated;
grant execute on function public.can_access_camp(uuid) to authenticated;
grant execute on function public.resync_identity_sequences() to authenticated;

-- ---------------------------------------------------------------------------
-- Server-side direct connections (python/psycopg) run as the `postgres` role.
-- They impersonate the signed-in user by SET ROLE authenticated and setting
-- request.jwt.claims, so RLS is enforced on every query the app issues.
-- ---------------------------------------------------------------------------
do $$
begin
    if not exists (
        select 1 from pg_auth_members
        where member = 'postgres'::regrole and roleid = 'authenticated'::regrole
    ) then
        execute 'grant authenticated to postgres';
    end if;
end
$$;

-- =============================================================================
-- tests/local_supabase_stub.sql
-- LOCAL TEST ONLY (Docker postgres:16-alpine).
-- Recreates the Supabase-specific prerequisites our migrations depend on:
--   roles anon/authenticated/service_role, schema auth, auth.users, auth.uid().
-- Never run against a real Supabase project (those objects already exist).
-- =============================================================================

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role nologin;
    end if;
end
$$;

create schema if not exists auth;

create table if not exists auth.users (
    id                 uuid primary key default gen_random_uuid(),
    email              text unique,
    raw_user_meta_data jsonb not null default '{}'::jsonb,
    created_at         timestamptz not null default now()
);

-- Same contract as Supabase: auth.uid() reads the JWT `sub` claim
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select nullif(coalesce(
        current_setting('request.jwt.claim.sub', true),
        nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'
    ), '')::uuid
$$;

grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to public;

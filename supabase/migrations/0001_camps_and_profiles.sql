-- =============================================================================
-- 0001_camps_and_profiles.sql
-- Rural Healthcare Multilingual Feedback Agent — Supabase phase 1
--
-- Purpose : camps (multi-camp support) + profiles (Supabase Auth <-> role/camp)
-- Target  : Supabase SQL Editor (free tier). Safe to re-run (idempotent).
-- Notes   : No secrets, no credentials, no patient data in this file.
-- =============================================================================

create extension if not exists pgcrypto;  -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- 1. Camps : one row per healthcare camp
-- ---------------------------------------------------------------------------
create table if not exists public.camps (
    id          uuid primary key default gen_random_uuid(),
    name        text not null unique,
    created_at  timestamptz not null default now()
);

comment on table public.camps is
    'Healthcare camps. Every feedback session belongs to exactly one camp.';

-- Fixed "Default Camp" used by legacy/local data and by accounts that have
-- not been reassigned yet. Never deleted (sessions reference it).
insert into public.camps (id, name)
values ('00000000-0000-0000-0000-000000000001', 'Default Camp')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- 2. Profiles : maps a Supabase Auth user to a role and (optionally) a camp
--
--    role = 'camp_staff' -> camp_id NOT NULL (enforced by CHECK)
--    role = 'admin'      -> camp_id NULL     : sees every camp
--                           camp_id NOT NULL : sees only that camp
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
    user_id     uuid primary key references auth.users (id) on delete cascade,
    email       text,
    role        text not null default 'camp_staff'
                check (role in ('camp_staff', 'admin')),
    camp_id     uuid references public.camps (id) on delete restrict,
    created_at  timestamptz not null default now(),
    constraint staff_must_have_an_authorized_camp
        check (role = 'admin' or camp_id is not null)
);

comment on table public.profiles is
    'Authorization data for Supabase Auth users. Never contains patient data.';

create index if not exists idx_profiles_camp_id on public.profiles (camp_id);

-- ---------------------------------------------------------------------------
-- 3. Helper functions used by Row Level Security policies.
--    SECURITY DEFINER so that a user can resolve their own role/camp without
--    recursing into the profiles RLS policies. search_path is pinned empty.
-- ---------------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.profiles p
        where p.user_id = auth.uid()
          and p.role = 'admin'
    );
$$;

create or replace function public.my_camp_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
    select p.camp_id
    from public.profiles p
    where p.user_id = auth.uid();
$$;

-- Single source of truth for camp-scoped access:
--   camp staff : only their own camp
--   admin      : their camp if set, otherwise all camps
create or replace function public.can_access_camp(p_camp_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.profiles p
        where p.user_id = auth.uid()
          and (
                (p.role = 'admin'
                     and (p.camp_id is null or p.camp_id = p_camp_id))
             or (p.role = 'camp_staff'
                     and p.camp_id = p_camp_id)
              )
    );
$$;

-- ---------------------------------------------------------------------------
-- 4. Auto-create a profile when a new Supabase Auth user is created.
--    Role / camp can be supplied in the user's metadata:
--      raw_user_meta_data = {"role": "camp_staff", "camp_id": "<uuid>"}
--    Missing/invalid values fall back to camp_staff + Default Camp.
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_role text := coalesce(new.raw_user_meta_data ->> 'role', 'camp_staff');
    v_camp uuid;
begin
    begin
        v_camp := nullif(coalesce(new.raw_user_meta_data ->> 'camp_id', ''), '')::uuid;
    exception when invalid_text_representation then
        v_camp := null;
    end;

    if v_role not in ('camp_staff', 'admin') then
        v_role := 'camp_staff';
    end if;

    -- camp_staff always falls back to the Default Camp; admins keep a NULL
    -- camp_id (meaning "sees every camp") unless one was supplied.
    if v_camp is null and v_role = 'camp_staff' then
        v_camp := '00000000-0000-0000-0000-000000000001';
    end if;

    insert into public.profiles (user_id, email, role, camp_id)
    values (new.id, new.email, v_role, v_camp)
    on conflict (user_id) do nothing;

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- 5. Grants (least privilege). Full table privileges are tightened in 0003.
-- ---------------------------------------------------------------------------
grant usage on schema public to anon, authenticated;
grant execute on function public.is_admin() to authenticated;
grant execute on function public.my_camp_id() to authenticated;
grant execute on function public.can_access_camp(uuid) to authenticated;

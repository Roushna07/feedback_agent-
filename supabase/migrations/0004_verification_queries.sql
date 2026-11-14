-- =============================================================================
-- 0004_verification_queries.sql
-- Rural Healthcare Multilingual Feedback Agent — Supabase phase 1
--
-- Purpose : READ-ONLY checks. Run these in the Supabase SQL Editor AFTER the
--           schema migration and after the SQLite data import.
--           Nothing here modifies data.
-- =============================================================================

-- 1. RLS is enabled on every exposed table -------------------------------
select relname as table_name, relrowsecurity as rls_enabled
from pg_class
where relnamespace = 'public'::regnamespace
  and relname in ('camps', 'profiles', 'feedback_sessions', 'feedback_answers')
order by relname;

-- 2. Policies present per table ------------------------------------------
select schemaname, tablename, policyname, cmd, roles
from pg_policies
where schemaname = 'public'
order by tablename, policyname;

-- 3. anon must have ZERO table privileges --------------------------------
select grantee, table_name, privilege_type
from information_schema.role_table_grants
where table_schema = 'public' and grantee = 'anon'
order by table_name;

-- 4. Table row counts (compare against the SQLite report) -----------------
select 'camps' as tbl, count(*) from public.camps
union all
select 'profiles', count(*) from public.profiles
union all
select 'feedback_sessions', count(*) from public.feedback_sessions
union all
select 'feedback_answers', count(*) from public.feedback_answers;

-- 5. Foreign key integrity: answers must reference existing sessions ------
select count(*) as orphan_answers
from public.feedback_answers a
left join public.feedback_sessions s on s.id = a.session_id
where s.id is null;

-- 6. Answer uniqueness (session_id, question_number) ----------------------
select session_id, question_number, count(*) as c
from public.feedback_answers
group by session_id, question_number
having count(*) > 1;

-- 7. Original transcripts preserved (should match SQLite non-empty count) --
select count(*) as answers_with_transcript
from public.feedback_answers
where coalesce(transcript, '') <> '';

-- 8. Translation status distribution --------------------------------------
select translation_status, count(*)
from public.feedback_answers
group by translation_status
order by count(*) desc;

-- 9. Identity sequence positions (must be > max(id) after import) ---------
--    If not, run:  select public.resync_identity_sequences();
select sequencename, last_value
from pg_sequences
where schemaname = 'public'
  and sequencename in ('feedback_sessions_id_seq', 'feedback_answers_id_seq');

select max(id) as max_session_id from public.feedback_sessions;
select max(id) as max_answer_id from public.feedback_answers;

-- 10. Camp coverage: every session belongs to an existing camp ------------
select count(*) as sessions_without_camp
from public.feedback_sessions s
left join public.camps c on c.id = s.camp_id
where c.id is null;

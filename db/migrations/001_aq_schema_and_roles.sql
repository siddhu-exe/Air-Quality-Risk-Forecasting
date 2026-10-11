-- 001_aq_schema_and_roles
-- Private schema "aq" for the live pipeline. It is NOT added to the Supabase API
-- "exposed schemas" list, so the auto-generated REST API cannot see it.
-- Defence in depth: nothing is granted to anon / authenticated / PUBLIC here, and
-- migration 006 enables RLS on every table with policies only for our two roles.
--
-- Roles are created WITHOUT a password and cannot log in until you set one by hand:
--   ALTER ROLE api_readonly PASSWORD '...';   -- run in the Supabase SQL editor
--   ALTER ROLE job_writer   PASSWORD '...';
-- Passwords never appear in migrations, the repo, or this assistant's context.
-- Pooler user names are "<role>.<project-ref>" (e.g. api_readonly.pxesptnmjxvxaygwgmjd).

create schema if not exists aq;
comment on schema aq is 'Delhi AQ live pipeline: readings, forecasts, scores, job log. Not exposed via the REST API.';

revoke all on schema aq from public;
revoke all on schema aq from anon, authenticated;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'api_readonly') then
    create role api_readonly login noinherit nosuperuser nocreatedb nocreaterole;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'job_writer') then
    create role job_writer login noinherit nosuperuser nocreatedb nocreaterole;
  end if;
end
$$;

-- Keep a small free-tier pooler from being exhausted by one client.
alter role api_readonly connection limit 10;
alter role job_writer   connection limit 5;

alter role api_readonly set search_path = aq;
alter role job_writer   set search_path = aq;
alter role api_readonly set timezone = 'Asia/Kolkata';
alter role job_writer   set timezone = 'Asia/Kolkata';
alter role api_readonly set statement_timeout = '10s';
alter role job_writer   set statement_timeout = '60s';
-- A role that can only read must not be able to write even by accident.
alter role api_readonly set default_transaction_read_only = on;

grant usage on schema aq to api_readonly, job_writer;

-- ModShare backend for Easy SCSModManager.
-- Run once in the Supabase SQL editor of the project, then put the project
-- URL and the publishable key into integrations/supabase/share_api.py.
--
-- Access model: RLS is enabled with NO policies, so the anon key cannot
-- touch the table directly. The only doors are the two SECURITY DEFINER
-- functions below - no enumeration, no updates, no deletes from clients.

create table if not exists mod_shares (
  code         text primary key check (code ~ '^[A-HJ-NP-Z2-9]{6}$'),
  game         text not null check (game in ('ets2', 'ats')),
  profile_name text not null default '',
  mod_count    int  not null check (mod_count between 1 and 2000),
  payload      jsonb not null check (pg_column_size(payload) < 262144),
  created_at   timestamptz not null default now()
);

alter table mod_shares enable row level security;
revoke all on table mod_shares from anon, authenticated;

-- Server-side code generation: same alphabet the client validates against
-- (no I/O/0/1 lookalikes), retried on the rare collision.
create or replace function create_share(p_game text, p_profile_name text, p_payload jsonb)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_code  text;
  v_count int;
  v_tries int := 0;
begin
  v_count := coalesce(jsonb_array_length(p_payload->'mods'), 0);
  loop
    select string_agg(substr('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', (floor(random() * 32))::int + 1, 1), '')
      into v_code
      from generate_series(1, 6);
    begin
      insert into mod_shares (code, game, profile_name, mod_count, payload)
      values (v_code, p_game, left(p_profile_name, 80), v_count, p_payload);
      return v_code;
    exception when unique_violation then
      v_tries := v_tries + 1;
      if v_tries > 5 then
        raise;
      end if;
    end;
  end loop;
end;
$$;

create or replace function get_share(p_code text)
returns jsonb
language sql
security definer
stable
set search_path = public
as $$
  select payload from mod_shares where code = upper(p_code);
$$;

grant execute on function create_share(text, text, jsonb) to anon;
grant execute on function get_share(text) to anon;

-- Cleanup: shares expire after 90 days. Needs the pg_cron extension
-- (Dashboard -> Database -> Extensions -> enable pg_cron) BEFORE this line.
select cron.schedule(
  'modshare-cleanup',
  '17 3 * * *',
  $$delete from mod_shares where created_at < now() - interval '90 days'$$
);

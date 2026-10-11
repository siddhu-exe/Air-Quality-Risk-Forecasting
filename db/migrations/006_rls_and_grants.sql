-- 006_rls_and_grants
-- RLS is enabled on every table. The only policies are for api_readonly (read) and job_writer
-- (read/insert/update). There are no policies for anon / authenticated, and the schema is not
-- exposed over REST, so those roles see nothing even if exposure were switched on by mistake.
-- RLS is not FORCEd: the table owner (postgres, used for migrations) is unaffected.
-- Neither role gets DELETE or TRUNCATE.

do $$
declare
  t text;
begin
  foreach t in array array[
    'stations', 'live_readings', 'live_aqi', 'job_runs', 'model_registry',
    'forecasts', 'forecast_scores', 'skill_rolling'
  ]
  loop
    execute format('alter table aq.%I enable row level security', t);
    execute format('create policy %I on aq.%I for select to api_readonly, job_writer using (true)', t || '_select', t);
    execute format('revoke all on aq.%I from public, anon, authenticated', t);
    execute format('grant select on aq.%I to api_readonly', t);
  end loop;
end
$$;

-- job_writer: insert + update (+ select, needed by ON CONFLICT DO UPDATE) on the tables it writes.
do $$
declare
  t text;
begin
  foreach t in array array[
    'stations', 'live_readings', 'live_aqi', 'job_runs', 'model_registry',
    'forecasts', 'forecast_scores', 'skill_rolling'
  ]
  loop
    execute format('create policy %I on aq.%I for insert to job_writer with check (true)', t || '_insert', t);
    execute format('create policy %I on aq.%I for update to job_writer using (true) with check (true)', t || '_update', t);
    execute format('grant select, insert, update on aq.%I to job_writer', t);
  end loop;
end
$$;

-- identity columns need sequence usage for inserts
grant usage on all sequences in schema aq to job_writer;

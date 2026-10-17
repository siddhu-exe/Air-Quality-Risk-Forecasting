-- 010_job_runs_stale_status
-- 'stale': the source answered but has no fresh reading (it is lagging). A data condition, not a failed run: the ingest exits 0,
-- the freshness check and the model-health page report the lag, and the "3 failed runs in a row" alert rule does not count it.

alter table aq.job_runs drop constraint job_runs_status_chk;
alter table aq.job_runs
  add constraint job_runs_status_chk check (status in ('running', 'success', 'partial', 'stale', 'failed'));

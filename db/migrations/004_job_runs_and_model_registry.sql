-- 004_job_runs_and_model_registry

create table aq.job_runs (
  id           bigint generated always as identity primary key,
  job          text        not null,                       -- 'ingest' | 'forecast' | 'score' | 'backfill' | ...
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  status       text        not null default 'running',
  rows_written integer,
  error        text,                                       -- short message only; never a connection string or key
  details      jsonb       not null default '{}'::jsonb,   -- e.g. per-station skip reasons
  github_run   text,                                       -- GITHUB_RUN_ID, for tracing
  constraint job_runs_status_chk check (status in ('running', 'success', 'partial', 'failed'))
);
create index job_runs_job_started_idx on aq.job_runs (job, started_at desc);

-- One row per deployable artifact. forecasts.model_version points here, so a forecast can only be
-- written for a registered model. The forecast job verifies sha256 against the file before use.
create table aq.model_registry (
  model_version    text primary key,                       -- e.g. 'aqi-1h-lgb-v1'
  model_name       text        not null,
  horizon          smallint    not null,
  target           text        not null,
  file             text        not null,                   -- repo-relative path
  sha256           text        not null,
  training_window  text,
  metrics_source   text,                                   -- repo path of the metrics table this model's skill comes from
  library_versions jsonb       not null default '{}'::jsonb,
  active           boolean     not null default true,
  created_at       timestamptz not null default now(),
  constraint model_registry_horizon_chk check (horizon in (1, 6, 24)),
  constraint model_registry_target_chk  check (target in ('aqi', 'pm25')),
  constraint model_registry_sha_chk     check (sha256 ~ '^[0-9a-f]{64}$'),
  constraint model_registry_no_pm25_24h check (not (target = 'pm25' and horizon = 24))
);

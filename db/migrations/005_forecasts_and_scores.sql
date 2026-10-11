-- 005_forecasts_and_scores
-- forecasts: one row per (issue_time, station, horizon, target). issue_time = the hour the forecast
-- was made from; target_time = issue_time + horizon. q10/q50/q90 hold the conformal-adjusted
-- interval where one exists (24h AQI only); p_severe = P(AQI >= 401) (24h AQI only). NULL otherwise.
-- y_persistence = the current value copied forward, written on every row.

create table aq.forecasts (
  id            bigint generated always as identity primary key,
  issue_time    timestamptz      not null,
  target_time   timestamptz      not null,
  station_id    integer          not null references aq.stations (station_id),
  horizon       smallint         not null,
  target        text             not null,
  model_version text             not null references aq.model_registry (model_version),
  y_hat         double precision not null,
  q10           double precision,
  q50           double precision,
  q90           double precision,
  p_severe      double precision,
  y_persistence double precision not null,
  created_at    timestamptz      not null default now(),
  constraint forecasts_key unique (issue_time, station_id, horizon, target),
  constraint forecasts_horizon_chk  check (horizon in (1, 6, 24)),
  constraint forecasts_target_chk   check (target in ('aqi', 'pm25')),
  constraint forecasts_no_pm25_24h  check (not (target = 'pm25' and horizon = 24)),
  constraint forecasts_target_time_chk check (extract(epoch from (target_time - issue_time)) = horizon * 3600),
  constraint forecasts_interval_chk check (q10 is null or q90 is null or q10 <= q90),
  constraint forecasts_p_severe_chk check (p_severe is null or p_severe between 0 and 1)
);
-- latest forecast per station/horizon/target (API) and "which forecasts have matured" (scorer)
create index forecasts_latest_idx on aq.forecasts (station_id, horizon, target, issue_time desc);
create index forecasts_target_time_idx on aq.forecasts (target_time);

-- forecast_scores: one row per forecast once its target_time has passed and the actual is known.
create table aq.forecast_scores (
  forecast_id            bigint primary key references aq.forecasts (id) on delete cascade,
  actual                 double precision not null,
  abs_err                double precision not null,
  abs_err_persistence    double precision not null,
  in_interval            boolean,                          -- null when the forecast has no interval
  severe_actual          boolean,                          -- actual AQI >= 401 (AQI target only)
  scored_at              timestamptz not null default now()
);

-- skill_rolling: rolling-window summaries behind /model-health and the alert rules.
-- station_id NULL = all stations pooled.
create table aq.skill_rolling (
  id                bigint generated always as identity primary key,
  station_id        integer references aq.stations (station_id),
  horizon           smallint    not null,
  target            text        not null,
  window_end        date        not null,                  -- Asia/Kolkata calendar day
  window_days       smallint    not null default 30,
  n                 integer     not null,
  mae_model         double precision,
  mae_persistence   double precision,
  skill_mae         double precision,                      -- 1 - mae_model / mae_persistence
  n_interval        integer,
  coverage80        double precision,
  n_prob            integer,
  brier_model       double precision,
  brier_persistence double precision,
  computed_at       timestamptz not null default now(),
  constraint skill_rolling_key unique nulls not distinct (station_id, horizon, target, window_end, window_days),
  constraint skill_rolling_horizon_chk check (horizon in (1, 6, 24)),
  constraint skill_rolling_target_chk  check (target in ('aqi', 'pm25'))
);
create index skill_rolling_lookup_idx on aq.skill_rolling (horizon, target, window_end desc);

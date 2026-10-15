-- 008_window_update_reference_and_run_type
-- (1) forecasts.y_window_update: the window-update persistence reference for AQI forecasts, frozen at issue time like
--     y_persistence (readings can be revised later by upserts and backfills, so scoring never re-derives references).
--     Filled for every AQI horizon, NULL for PM2.5. When the current hourly AQI is missing at issue time the writer stores
--     y_persistence there (the same fallback the baseline evaluation used), so AQI rows always carry a reference.
-- (2) run_type: 'live' (the hourly job) or 'replay' (a historical hour re-forecast from stored readings). Replays share the
--     (issue_time, station, horizon, target) key with live rows; they cover past hours only, so they do not collide with
--     live issue hours. Model health and the API read run_type = 'live'.
-- (3) forecast_scores.abs_err_window_update and skill_rolling.{mae_window_update,skill_vs_window_update}, so health can show the second baseline.
-- Run on empty forecasts / forecast_scores / skill_rolling tables (the new CHECKs apply to every existing row).

alter table aq.forecasts
  add column y_window_update double precision,
  add column run_type        text not null default 'live',
  add constraint forecasts_run_type_chk check (run_type in ('live', 'replay')),
  add constraint forecasts_window_update_chk check ((target = 'aqi') = (y_window_update is not null));

alter table aq.forecast_scores
  add column abs_err_window_update double precision,
  add constraint forecast_scores_window_update_chk check ((target = 'aqi') = (abs_err_window_update is not null));

alter table aq.job_runs
  add column run_type text not null default 'live',
  add constraint job_runs_run_type_chk check (run_type in ('live', 'replay'));

-- skill_rolling is live-only: replays are scored into forecast_scores and reported from files, never into the rolling table.
alter table aq.skill_rolling
  add column mae_window_update      double precision,
  add column skill_vs_window_update double precision;

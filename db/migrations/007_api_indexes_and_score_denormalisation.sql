-- 007_api_indexes_and_score_denormalisation
-- Indexes for the API's queries, plus target_time (and the keys the API filters on) on
-- forecast_scores so model-health queries need no join. A composite foreign key makes the copied
-- columns impossible to get out of step with the forecast they describe.
-- (live_readings(ts) already exists from 003: live_readings_ts_idx. The primary keys cover
-- per-station lookups.) forecast_scores must be empty when this runs, because the new columns are NOT NULL.

-- "all forecasts for a station, newest first" (the 005 index leads with horizon/target as well)
create index forecasts_station_issue_idx on aq.forecasts (station_id, issue_time desc);

-- target of the composite foreign key below
alter table aq.forecasts
  add constraint forecasts_score_key unique (id, station_id, horizon, target, target_time);

alter table aq.forecast_scores
  add column station_id  integer     not null,
  add column horizon     smallint    not null,
  add column target      text        not null,
  add column target_time timestamptz not null;

alter table aq.forecast_scores
  add constraint forecast_scores_forecast_consistent_fk
  foreign key (forecast_id, station_id, horizon, target, target_time)
  references aq.forecasts (id, station_id, horizon, target, target_time)
  on delete cascade;

create index forecast_scores_target_time_idx on aq.forecast_scores (target_time);

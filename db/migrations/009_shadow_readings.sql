-- 009_shadow_readings
-- Readings from a source that is being evaluated but must never feed forecasts or the API (WAQI, back-converted from
-- US-EPA sub-indices). A separate table, not live_readings: that table has one row per (station, hour), so a second source for
-- the same hour would overwrite or be overwritten by the primary source, and the forecast job reads it without a source filter.
-- Only job_writer can read or write this table. api_readonly has no grant and no policy here, so the API cannot see it.

create table aq.shadow_readings (
  station_id  integer          not null references aq.stations (station_id),
  ts          timestamptz      not null,                       -- hour label: the feed time floored to the hour (Asia/Kolkata)
  source      text             not null,                       -- 'waqi_backconverted'
  pm25        double precision,
  pm10        double precision,
  no2         double precision,
  so2         double precision,
  co          double precision,
  o3          double precision,
  raw_iaqi    jsonb            not null default '{}'::jsonb,   -- the sub-indices as published
  waqi_time   timestamptz      not null,                       -- the feed's own timestamp
  ingested_at timestamptz      not null default now(),
  primary key (station_id, ts, source),
  constraint shadow_readings_nonneg_chk check (
    coalesce(pm25, 0) >= 0 and coalesce(pm10, 0) >= 0 and coalesce(no2, 0) >= 0 and
    coalesce(so2, 0) >= 0 and coalesce(co, 0) >= 0 and coalesce(o3, 0) >= 0)
);
create index shadow_readings_ts_idx on aq.shadow_readings (ts desc);
comment on table aq.shadow_readings is 'Shadow-mode source readings (WAQI back-converted). Never read by the forecast job or the API.';

alter table aq.shadow_readings enable row level security;
revoke all on aq.shadow_readings from public, anon, authenticated, api_readonly;
create policy shadow_readings_select on aq.shadow_readings for select to job_writer using (true);
create policy shadow_readings_insert on aq.shadow_readings for insert to job_writer with check (true);
create policy shadow_readings_update on aq.shadow_readings for update to job_writer using (true) with check (true);
grant select, insert, update on aq.shadow_readings to job_writer;

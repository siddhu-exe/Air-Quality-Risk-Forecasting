-- 003_live_readings_and_aqi
-- ts is the hour the reading belongs to (TIMESTAMPTZ; Asia/Kolkata at the edges, as in the
-- training pipeline). Whether the source labels the start or the end of the averaging hour is
-- verified in Stage 2 and handled in the ingest code, not here.
-- The composite primary key is the UNIQUE(station_id, ts) idempotency key for upserts.
-- Units match the training data: ug/m3, CO in mg/m3, degC, %, m/s, W/m2.

create table aq.live_readings (
  station_id      integer          not null references aq.stations (station_id),
  ts              timestamptz      not null,
  pm25            double precision,
  pm10            double precision,
  no2             double precision,
  nox             double precision,
  nh3             double precision,
  so2             double precision,
  co              double precision,
  o3              double precision,
  temperature     double precision,
  humidity        double precision,
  wind_speed      double precision,
  solar_radiation double precision,
  weather_source  text,                                   -- e.g. 'open-meteo'; null when weather is missing
  qc_flags        jsonb            not null default '{}'::jsonb,  -- {"pm25": "sentinel", ...}; flagged cells are nullified, not the row
  source          text             not null,              -- 'data.gov.in' | 'openaq' | ...
  ingested_at     timestamptz      not null default now(),
  primary key (station_id, ts),
  -- same physical bounds as etl/schemas.py PHYSICAL_BOUNDS (bad cells are NULLed before insert)
  constraint live_readings_pollutants_chk check (
    coalesce(pm25, 0) >= 0 and coalesce(pm10, 0) >= 0 and coalesce(no2, 0) >= 0 and
    coalesce(nox, 0)  >= 0 and coalesce(nh3, 0)  >= 0 and coalesce(so2, 0) >= 0 and
    coalesce(co, 0)   >= 0 and coalesce(o3, 0)   >= 0),
  constraint live_readings_humidity_chk check (humidity is null or humidity between 0 and 100),
  constraint live_readings_wind_chk     check (wind_speed is null or wind_speed >= 0),
  constraint live_readings_solar_chk    check (solar_radiation is null or solar_radiation >= 0)
);
create index live_readings_ts_idx on aq.live_readings (ts desc);

create table aq.live_aqi (
  station_id    integer          not null references aq.stations (station_id),
  ts            timestamptz      not null,
  aqi           double precision not null,
  aqi_source    text             not null default 'recomputed_live',
  n_pollutants  smallint,                                 -- sub-indices available this hour
  n_valid_hours smallint,                                 -- valid hours inside the 24h rolling window
  computed_at   timestamptz      not null default now(),
  primary key (station_id, ts),
  constraint live_aqi_source_chk check (aqi_source = 'recomputed_live'),
  constraint live_aqi_range_chk  check (aqi between 0 and 500)
);
create index live_aqi_ts_idx on aq.live_aqi (ts desc);
comment on table aq.live_aqi is 'AQI recomputed from live pollutants with src/features/compute_cpcb_aqi.py. NOT the official CPCB value.';

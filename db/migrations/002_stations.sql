-- 002_stations
-- Same station_id values (3..9) as STATION_IDS in src/features/compute_cpcb_aqi.py, so the
-- unchanged feature code keeps working. Rows are loaded by src/live/load_stations.py, not here.

create table aq.stations (
  station_id         integer primary key,
  station_name       text        not null unique,   -- canonical name used by the feature code
  feed_name          text        unique,            -- name as the live feed spells it; filled after the first real fetch
  city               text        not null default 'Delhi',
  operator           text,
  latitude           numeric(9, 6),
  longitude          numeric(9, 6),
  coords_approximate boolean     not null default true,  -- true until coordinates come from the feed / an official list
  created_at         timestamptz not null default now(),
  constraint stations_lat_chk check (latitude  is null or latitude  between -90  and 90),
  constraint stations_lon_chk check (longitude is null or longitude between -180 and 180)
);
comment on column aq.stations.coords_approximate is 'true = hand-entered approximate coordinates (from src/features/exogenous_drivers.py), not an official list.';

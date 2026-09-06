-- 002_create_tables.sql

CREATE TABLE IF NOT EXISTS stations (
    station_id      SERIAL PRIMARY KEY,
    station_name    TEXT NOT NULL UNIQUE,
    station_folder  TEXT,
    city            TEXT,
    operator        TEXT,
    data_from       DATE,
    data_to         DATE
);

CREATE TABLE IF NOT EXISTS source_files (
    source_file_id  SERIAL PRIMARY KEY,
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL UNIQUE,
    source_type     TEXT NOT NULL, -- 'CAAQMS' or 'AQI'
    station_id      INT REFERENCES stations(station_id),
    file_format     TEXT,
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    file_row_count  INT,
    loaded_at       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    processing_status TEXT,
    processing_error  TEXT
);

CREATE TABLE IF NOT EXISTS caaqms_hourly (
    id              BIGSERIAL PRIMARY KEY,
    station_id      INT REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,
    pm25            NUMERIC(8,2),
    pm10            NUMERIC(8,2),
    no_ugm3         NUMERIC(8,2),
    no2_ugm3        NUMERIC(8,2),
    nox_ppb         NUMERIC(8,2),
    nh3_ugm3        NUMERIC(8,2),
    so2_ugm3        NUMERIC(8,2),
    co_mgm3         NUMERIC(8,4),
    ozone_ugm3      NUMERIC(8,2),
    benzene_ugm3    NUMERIC(8,4),
    toluene_ugm3    NUMERIC(8,4),
    xylene_ugm3     NUMERIC(8,4),
    o_xylene_ugm3   NUMERIC(8,4),
    eth_benzene_ugm3 NUMERIC(8,4),
    mp_xylene_ugm3  NUMERIC(8,4),
    temp_c          NUMERIC(6,2),
    rh_pct          NUMERIC(6,2),
    ws_ms           NUMERIC(6,2),
    wd_deg          NUMERIC(6,2),
    rf_mm           NUMERIC(6,2),
    tot_rf_mm       NUMERIC(6,2),
    sr_wm2          NUMERIC(8,2),
    bp_mmhg         NUMERIC(8,2),
    vws_ms          NUMERIC(6,2),
    source_file_id  INT REFERENCES source_files(source_file_id),
    UNIQUE (station_id, ts)
);

CREATE TABLE IF NOT EXISTS aqi_hourly (
    id              BIGSERIAL PRIMARY KEY,
    station_id      INT REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,
    aqi             NUMERIC(6,1),
    source_file_id  INT REFERENCES source_files(source_file_id),
    UNIQUE (station_id, ts)
);

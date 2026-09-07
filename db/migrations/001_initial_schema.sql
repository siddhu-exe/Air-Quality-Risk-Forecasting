-- db/migrations/001_initial_schema.sql

-- Enable necessary extensions (if any, keep it minimal for now)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. stations: Dimension table mapping unique sensor locations
CREATE TABLE IF NOT EXISTS stations (
    station_id SERIAL PRIMARY KEY,
    station_name VARCHAR(255) NOT NULL,
    raw_folder_name VARCHAR(255) NOT NULL,  -- Traceable metadata mapping backward
    city VARCHAR(100) NOT NULL,
    operator VARCHAR(100),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    coverage_start_date DATE,
    coverage_end_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. source_files: Data lineage & ETL observability table
CREATE TABLE IF NOT EXISTS source_files (
    source_file_id SERIAL PRIMARY KEY,
    station_id INT REFERENCES stations(station_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    source_type VARCHAR(50),
    file_format VARCHAR(50),
    reporting_period_start TIMESTAMPTZ,
    reporting_period_end TIMESTAMPTZ,
    row_count INT,
    processing_status VARCHAR(50),
    load_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. caaqms_hourly: Curated hourly pollutant and environmental measurements
CREATE TABLE IF NOT EXISTS caaqms_hourly (
    caaqms_hourly_id BIGSERIAL PRIMARY KEY,
    station_id INT REFERENCES stations(station_id) ON DELETE CASCADE,
    source_file_id INT REFERENCES source_files(source_file_id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,

    -- Core Pollutants
    pm25 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    no_ugm3 DOUBLE PRECISION,
    no2_ugm3 DOUBLE PRECISION,
    nox_ppb DOUBLE PRECISION,
    nh3_ugm3 DOUBLE PRECISION,
    so2_ugm3 DOUBLE PRECISION,
    co_mgm3 DOUBLE PRECISION,
    ozone_ugm3 DOUBLE PRECISION,
    benzene_ugm3 DOUBLE PRECISION,
    toluene_ugm3 DOUBLE PRECISION,
    xylene_ugm3 DOUBLE PRECISION,
    o_xylene_ugm3 DOUBLE PRECISION,
    eth_benzene_ugm3 DOUBLE PRECISION,
    mp_xylene_ugm3 DOUBLE PRECISION,

    -- Core Environmental
    temp_c DOUBLE PRECISION,
    rh_pct DOUBLE PRECISION,
    ws_ms DOUBLE PRECISION,
    wd_deg DOUBLE PRECISION,
    rf_mm DOUBLE PRECISION,
    tot_rf_mm DOUBLE PRECISION,
    sr_wm2 DOUBLE PRECISION,
    bp_mmhg DOUBLE PRECISION,
    vws_ms DOUBLE PRECISION,

    -- Quality Control
    qc_flags JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Constraint enforcing deduplication per logical time window
    CONSTRAINT uq_caaqms_hourly_station_ts UNIQUE (station_id, ts)
);

-- 4. aqi_hourly: Curated hourly AQI Observations
CREATE TABLE IF NOT EXISTS aqi_hourly (
    aqi_hourly_id BIGSERIAL PRIMARY KEY,
    station_id INT REFERENCES stations(station_id) ON DELETE CASCADE,
    source_file_id INT REFERENCES source_files(source_file_id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    aqi_value DOUBLE PRECISION,

    -- Quality Control
    qc_flags JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Constraint enforcing deduplication per logical time window
    CONSTRAINT uq_aqi_hourly_station_ts UNIQUE (station_id, ts)
);

-- 5. Time-Series specific index tuning
CREATE INDEX IF NOT EXISTS idx_caaqms_ts ON caaqms_hourly(ts);
CREATE INDEX IF NOT EXISTS idx_aqi_ts ON aqi_hourly(ts);

-- Speed up lineage/auditing queries linking rows back to originating files
CREATE INDEX IF NOT EXISTS idx_caaqms_source_file ON caaqms_hourly(source_file_id);
CREATE INDEX IF NOT EXISTS idx_aqi_source_file ON aqi_hourly(source_file_id);

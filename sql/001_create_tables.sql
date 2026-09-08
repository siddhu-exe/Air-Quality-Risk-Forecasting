-- 001_create_tables.sql

CREATE TABLE IF NOT EXISTS stations (
    station_id SERIAL PRIMARY KEY,
    station_name TEXT NOT NULL,
    raw_folder_name TEXT NOT NULL,
    city TEXT NOT NULL,
    operator TEXT,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    coverage_start_date DATE,
    coverage_end_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_files (
    source_file_id SERIAL PRIMARY KEY,
    station_id INT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    source_type TEXT,
    file_format TEXT,
    reporting_period_start TIMESTAMPTZ,
    reporting_period_end TIMESTAMPTZ,
    row_count INT,
    processing_status TEXT,
    load_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS caaqms_hourly (
    caaqms_hourly_id BIGSERIAL PRIMARY KEY,
    station_id INT NOT NULL,
    source_file_id INT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Using the names defined in the user prompt (ETL will need a tiny mapping adjustment or DB uses ETL names.
    -- Decided to use the exact names from ETL `schemas.py` to prevent rewriting validated ETL code, 
    -- BUT I will alias them in the python loader or use the exact prompt names. 
    -- Prompt says: "caaqms_hourly... pm25, pm10, no, no2, nox, nh3, so2, co, o3, benzene, toluene, xylene, temperature, humidity, wind_speed, wind_direction, rainfall, solar_radiation, barometric_pressure, vertical_wind_speed".
    -- Let's stick to the prompt's explicit ERD names to satisfy the requirement, and we will handle the Python ETL rename later.
    pm25 NUMERIC(10, 2),
    pm10 NUMERIC(10, 2),
    no NUMERIC(10, 2),
    no2 NUMERIC(10, 2),
    nox NUMERIC(10, 2),
    nh3 NUMERIC(10, 2),
    so2 NUMERIC(10, 2),
    co NUMERIC(10, 2),
    o3 NUMERIC(10, 2),
    benzene NUMERIC(10, 2),
    toluene NUMERIC(10, 2),
    xylene NUMERIC(10, 2),
    temperature NUMERIC(10, 2),
    humidity NUMERIC(10, 2),
    wind_speed NUMERIC(10, 2),
    wind_direction NUMERIC(10, 2),
    rainfall NUMERIC(10, 2),
    solar_radiation NUMERIC(10, 2),
    barometric_pressure NUMERIC(10, 2),
    vertical_wind_speed NUMERIC(10, 2),
    
    qc_flags JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS aqi_hourly (
    aqi_hourly_id BIGSERIAL PRIMARY KEY,
    station_id INT NOT NULL,
    source_file_id INT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    aqi_value NUMERIC(10, 2),
    qc_flags JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

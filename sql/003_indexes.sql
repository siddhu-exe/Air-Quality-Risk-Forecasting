-- 003_indexes.sql

-- The UNIQUE(station_id, timestamp) constraints automatically create btree indexes 
-- structurally identical to (station_id ASC, timestamp ASC). 
-- This efficiently serves queries filtering by `station_id` alone, AND `station_id` + `timestamp` queries.
-- Thus, creating a separate index on just `station_id` is redundant and omitted.

-- 1. Index on `timestamp` alone is highly necessary for time-based analytical slices 
-- across ALL stations (e.g., extracting all Delhi pollutant values for "2025-01-01").
CREATE INDEX IF NOT EXISTS idx_caaqms_timestamp ON caaqms_hourly(timestamp);
CREATE INDEX IF NOT EXISTS idx_aqi_timestamp ON aqi_hourly(timestamp);

-- 2. Index on `source_file_id` is required for ETL lineage audits (e.g. deleting all rows 
-- produced by a specific corrupted file quickly).
CREATE INDEX IF NOT EXISTS idx_caaqms_source_file ON caaqms_hourly(source_file_id);
CREATE INDEX IF NOT EXISTS idx_aqi_source_file ON aqi_hourly(source_file_id);
CREATE INDEX IF NOT EXISTS idx_source_files_load_ts ON source_files(load_timestamp);

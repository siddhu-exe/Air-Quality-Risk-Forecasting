-- 003_indexes.sql

-- Index by timestamp to allow fast temporal queries
CREATE INDEX IF NOT EXISTS idx_caaqms_ts ON caaqms_hourly (ts);
CREATE INDEX IF NOT EXISTS idx_aqi_ts ON aqi_hourly (ts);

-- The UNIQUE constraints (station_id, ts) already create an implicit B-Tree index on (station_id, ts)
-- which is optimal for our UPSERT (ON CONFLICT) and also for querying a specific station's time series.

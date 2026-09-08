-- 005_validation_data.sql
-- Pre-ingestion empty state checks / readiness checks

-- Ensure no duplicate station_id + timestamp combos exist (should be 0)
SELECT station_id, timestamp, COUNT(*) 
FROM caaqms_hourly 
GROUP BY station_id, timestamp 
HAVING COUNT(*) > 1;

-- Ensure no null foreign keys (should be 0)
SELECT COUNT(*) FROM caaqms_hourly WHERE station_id IS NULL OR source_file_id IS NULL;
SELECT COUNT(*) FROM aqi_hourly WHERE station_id IS NULL OR source_file_id IS NULL;

-- Validate impossible timestamp ranges (e.g. future dates or before sensors existed)
SELECT COUNT(*) FROM caaqms_hourly WHERE timestamp > NOW();
SELECT COUNT(*) FROM aqi_hourly WHERE timestamp < '2000-01-01'::TIMESTAMPTZ;

-- Check extreme invalid AQI values (India AQI maxes at 500, but some outliers hit 999. Above 1500 is safely impossible raw data)
SELECT COUNT(*) FROM aqi_hourly WHERE aqi_value > 1500 OR aqi_value < 0;

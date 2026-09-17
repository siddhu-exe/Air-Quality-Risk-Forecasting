#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

export PGHOST=127.0.0.1
export PGPORT=5433
export PGUSER=aq_admin
export PGDATABASE=air_quality_db

echo "--- 1. Applying Migrations ---"
psql -f sql/001_create_tables.sql
psql -f sql/002_constraints.sql
psql -f sql/003_indexes.sql

echo ""
echo "--- 2. Schema Validation ---"
psql -f sql/004_validation_schema.sql

echo ""
echo "--- 3. Pre-Ingestion Data Validation ---"
psql -f sql/005_validation_data.sql

echo ""
echo "--- 4. Synthetic Record Tests ---"

echo "Creating synthetic station and file..."
# We will use psql variables and returning bounds to prove it works.
psql << 'SQLEOF'
-- Set session timezone so any local rendering matches Indian Time
SET timezone = 'Asia/Kolkata';

DO $$ 
DECLARE
    new_station_id INT;
    new_file_id INT;
BEGIN
    INSERT INTO stations (station_name, raw_folder_name, city, operator)
    VALUES ('Test Station', 'Test Station, Delhi', 'Delhi', 'DPCC')
    RETURNING station_id INTO new_station_id;
    
    INSERT INTO source_files (station_id, filename, path, source_type)
    VALUES (new_station_id, 'test_data.csv', '/test/test_data.csv', 'CAAQMS')
    RETURNING source_file_id INTO new_file_id;

    -- Insert valid synthetic measurement with Asia/Kolkata explicitly cast
    RAISE NOTICE 'Inserting test row for Timestamps and JSONB...';
    INSERT INTO caaqms_hourly (station_id, source_file_id, timestamp, pm25, qc_flags)
    VALUES (new_station_id, new_file_id, '2026-08-01 14:00:00+05:30'::TIMESTAMPTZ, 45.2, '{"pm10": "SENTINEL_-999"}'::JSONB);
END $$;

-- Verify what was stored
SELECT station_id, 
       timestamp AS stored_ist_time, 
       timestamp AT TIME ZONE 'UTC' AS stored_utc_time,
       qc_flags 
FROM caaqms_hourly 
WHERE qc_flags IS NOT NULL LIMIT 1;

-- Test Unique Constraint Conflict
SELECT 'Testing UNIQUE Constraint violation handling...' AS next_step;
SQLEOF

# Try an intentional failure, suppressing normal output but checking exit code
echo "Attempting to insert exact duplicate timestamp for the same station..."
if psql -c "INSERT INTO caaqms_hourly (station_id, source_file_id, timestamp, pm25) VALUES ((SELECT station_id FROM stations LIMIT 1), (SELECT source_file_id FROM source_files LIMIT 1), '2026-08-01 14:00:00+05:30'::TIMESTAMPTZ, 100.0);" 2>/dev/null; then
    echo "❌ UNIQUE constraint failed! Allowed duplicate timestamp."
else
    echo "✅ UNIQUE constraint verified: Prevented duplicate station+timestamp insert."
fi

echo ""
echo "Cleaning up synthetic record via CASCADE..."
psql -c "DELETE FROM stations WHERE station_name = 'Test Station';"
echo "Remaining records in fact table (should be 0):"
psql -c "SELECT COUNT(*) FROM caaqms_hourly;"

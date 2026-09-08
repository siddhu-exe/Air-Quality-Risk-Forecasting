-- 006_fix_fk_delete_policy.sql
--
-- Purpose: Change all five ON DELETE CASCADE foreign keys to ON DELETE RESTRICT.
--
-- Rationale: This database is a curated, historical air-quality data warehouse.
-- Deleting a parent record (station or source_file) must NEVER silently destroy
-- downstream observations. RESTRICT forces the operator to explicitly remove child
-- rows first, making accidental mass-deletion of historical data impossible.
--
-- Scope: FK delete policy only. No table structure, columns, PKs, UNIQUE
-- constraints, indexes, or data types are altered.
--
-- Applied against: air_quality_db @ 127.0.0.1:5433

BEGIN;

-- ── source_files ──────────────────────────────────────────────────────────────
-- source_files.station_id → stations.station_id
ALTER TABLE source_files
    DROP CONSTRAINT fk_source_files_station,
    ADD  CONSTRAINT fk_source_files_station
         FOREIGN KEY (station_id)
         REFERENCES stations(station_id)
         ON DELETE RESTRICT
         ON UPDATE NO ACTION;

-- ── caaqms_hourly ─────────────────────────────────────────────────────────────
-- caaqms_hourly.station_id → stations.station_id
ALTER TABLE caaqms_hourly
    DROP CONSTRAINT fk_caaqms_station,
    ADD  CONSTRAINT fk_caaqms_station
         FOREIGN KEY (station_id)
         REFERENCES stations(station_id)
         ON DELETE RESTRICT
         ON UPDATE NO ACTION;

-- caaqms_hourly.source_file_id → source_files.source_file_id
ALTER TABLE caaqms_hourly
    DROP CONSTRAINT fk_caaqms_source_file,
    ADD  CONSTRAINT fk_caaqms_source_file
         FOREIGN KEY (source_file_id)
         REFERENCES source_files(source_file_id)
         ON DELETE RESTRICT
         ON UPDATE NO ACTION;

-- ── aqi_hourly ────────────────────────────────────────────────────────────────
-- aqi_hourly.station_id → stations.station_id
ALTER TABLE aqi_hourly
    DROP CONSTRAINT fk_aqi_station,
    ADD  CONSTRAINT fk_aqi_station
         FOREIGN KEY (station_id)
         REFERENCES stations(station_id)
         ON DELETE RESTRICT
         ON UPDATE NO ACTION;

-- aqi_hourly.source_file_id → source_files.source_file_id
ALTER TABLE aqi_hourly
    DROP CONSTRAINT fk_aqi_source_file,
    ADD  CONSTRAINT fk_aqi_source_file
         FOREIGN KEY (source_file_id)
         REFERENCES source_files(source_file_id)
         ON DELETE RESTRICT
         ON UPDATE NO ACTION;

COMMIT;

-- 002_constraints.sql
-- Foreign Keys
ALTER TABLE source_files
    ADD CONSTRAINT fk_source_files_station 
    FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE CASCADE;

ALTER TABLE caaqms_hourly
    ADD CONSTRAINT fk_caaqms_station 
    FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_caaqms_source_file 
    FOREIGN KEY (source_file_id) REFERENCES source_files(source_file_id) ON DELETE CASCADE;

ALTER TABLE aqi_hourly
    ADD CONSTRAINT fk_aqi_station 
    FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_aqi_source_file 
    FOREIGN KEY (source_file_id) REFERENCES source_files(source_file_id) ON DELETE CASCADE;

-- Unique Constraints for Idempotency
ALTER TABLE caaqms_hourly
    ADD CONSTRAINT uq_caaqms_hourly_station_ts UNIQUE (station_id, timestamp);

ALTER TABLE aqi_hourly
    ADD CONSTRAINT uq_aqi_hourly_station_ts UNIQUE (station_id, timestamp);

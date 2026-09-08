# LLM Context: Project Architecture & State

**Purpose:** Read this file to instantly understand the repository structure, previous bug fixes, constraints, and current state of the Air Quality Risk Forecasting system. Do not change project direction or introduce ML technologies prematurely.

## Project Scope & Lifecycle
**Lifecycle Pipeline:** RAW GOVERNMENT DATA -> DATA PROFILING -> DATABASE DESIGN -> ETL/DATA CLEANING -> POSTGRESQL -> DATA VALIDATION -> EDA -> FEATURE ENGINEERING -> AQI FORECASTING -> RISK CLASSIFICATION -> CAUSAL/POLICY ANALYSIS -> DASHBOARD.
**Current Stage:** ETL Validated -> ERD Completed -> **Moving to PostgreSQL Setup**.

## Geographic Scope
- **Primary:** Delhi (7 specific stations: Anand Vihar, Bawana, Dwarka-Sector 8, ITO, Jahangirpuri, Punjabi Bagh, R K Puram).
- **Secondary:** Mumbai data exists but MUST NOT be mixed into the primary Delhi dataset blindly. It is reserved for external validation later.

## Database ERD & Rules (Phase 3)
The PostgreSQL schema strictly implements **4 Core Tables** (no placeholder ML/Analytics tables yet):
1. `stations`: Dimension table. Canonical normalized representations.
2. `source_files`: Lineage tracking. `source_file_id` is its own PK. Identifies reporting periods and row counts per file.
3. `caaqms_hourly`: Hourly pollutants (pm25, nox_ppb, etc.) and environmental data (temp, rh, etc.).
4. `aqi_hourly`: Target metric tracking (the wide AQI files).
*Constraints:* `UNIQUE(station_id, timestamp)` on fact tables for idempotent `ON CONFLICT DO UPDATE` loads. Uses `TIMESTAMPTZ` set to `Asia/Kolkata`.

## Critical Data/ETL Bugs Solved (Must Maintain!)
1. **Epoch Bug Avoided:** AQI XLSX `Date` columns contain bare integers (1, 2...). We extract `YYYY-Month` from the filename using regex and concatenate it with the integer to reconstruct the exact `Asia/Kolkata` timestamp.
2. **Sentinel False Positives:** Values `9` and `-9` were triggering valid readings to nullify (e.g. 9°C). Sentinels are strictly bounded to extreme structural constants (`-999`, `-9999`, `9999`).
3. **Barometric Pressure Bounds:** `bp_mmhg=999.0` is an explicit physical clip error. Validation traps `bp_mmhg` bounded at `(400, 998.9)` to save genuine hPa scale readings (966-999).
4. **Invalid Measurement Row Retention:** A bad measurement nullifies the specific cell, NOT the row. The row remains, and a JSON log (e.g. `{"pm25": "SENTINEL_-999"}`) is stamped onto the row's `qc_flags` JSONB column.

## Current Dry-Run Data State (End of Phase 2 Validation)
- 112 processed files; 0 failures.
- 162,096 CAAQMS records retained.
- 59,717 AQI records retained (up from 1,932 prior to epoch bug fix).
- 930 out-of-bounds nullifications; 0 TS drops; 0 sentinel drops.
## Infrastructure Requirements
- **NO DOCKER:** Due to strictly constrained laptop computational resources, Docker is prohibited.
- **Database Engine:** We run a completely native, local, user-space PostgreSQL cluster via `initdb` stored securely inside `./local_pg_data` on port `5433`.
- **Start/Stop:** The environment is manually spun up via `pg_ctl -D local_pg_data start` to preserve battery and CPU when not actively ingesting data. 

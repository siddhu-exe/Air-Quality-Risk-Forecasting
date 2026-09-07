# LLM Context: Project Architecture & State

**Purpose:** Read this file to instantly understand the repository structure, previous bug fixes, constraints, and current state. This file saves you from reading dozens of codebase files.

## Project Summary
- **Domain:** Air Quality Risk Forecasting (Delhi & Mumbai).
- **Goal:** Clean raw sensor data (ETL), store it in PostgreSQL, then build ML forecasting models.
- **Stack:** Python 3, Pandas, numpy, openpyxl, PostgreSQL (planned).

## Directory Structure
- `/Og Data` -> Source data (never modify or delete these files).
  - `/Delhi data` -> Station dirs (e.g., `Anand Vihar, Delhi - DPCC`).
    - Contains `Raw Data/` (univariate CSVs, 2023-26) and `AQI Hourly/` (XLSX files, 2025).
    - **Quirk:** `Jahangirpuri, Delhi - DPCC\t` folder has a trailing tab character.
  - `/Mumbai data` -> City-level AQI XLSX files (Jan-Jul 2026).
- `/etl` -> The Python processing pipeline.
  - `pipeline.py`: Main orchestrator orchestrating dry-runs over all files.
  - `schemas.py`: Constants, column mapping to `snake_case`, validation boundaries.
  - `validation.py`: Cleans sentinels, checks bounds, generates `qc_flags` JSON.
  - `transform_caaqms.py`: Parses the Raw Delhi CSVs.
  - `transform_aqi.py`: Parses the AQI XLSX files (melt wide-to-long format).
- `/docs` -> Project documentation.
- `/.claude/projects/*/memory/` -> Persistent cross-session Claude memory.

## Critical Technical Quirks & Solved Bugs (DO NOT REGRESS)
1. **AQI Dates are Integers:** `Date` columns in AQI Excel spreadsheets are just day-of-month integers (1, 2, 3..). Parsing them directly yields `1970-01-01` epoch bugs. 
   *Fix:* `transform_aqi.py` extracts Year and Month using regex on the filename (`r"_(20\d{2})_([A-Za-z]+)_"`), then assembles a localized IST (`Asia/Kolkata`) timestamp.
2. **Sentinel False Positives:** Previously, values `9` and `-9` were treated as error sentinels. This destroyed valid readouts (e.g., 9°C, 9µg/m³ PM2.5).
   *Fix:* `schemas.py` restricts `SENTINEL_VALUES` strictly to structural errors: `{-999, -9999, 9999}`.
3. **hPa vs mmHg Physical Bounds:** Bawana Station logs `bp_mmhg` in **hPa** (960-999) despite the column name. `999.0` is a widely known sensor clip maximum. 
   *Fix:* Physical bound in `schemas.py` is dynamically set to `(400, 998.9)`. This successfully traps the `999.0` error without nullifying historically valid hPa outputs.
4. **Row Retention over Dropping:** When a cell violates a sentinel or physical bounds rule, the cell is converted to `np.nan` and documented in a JSON `qc_flags` column. **The row itself is never dropped** unless the timestamp is fundamentally unrecoverable.

## Current Pipeline Output Stats (End of Phase 2)
The ETL dry-run currently successfully processes 112 files yielding:
- CAAQMS Records: 162,096
- AQI Records: 59,717
- Invalid Timestamps Dropped: 0
- QC Flagged Rows: 930 (Almost exclusively `999.0` BP clip traps).

## Next Steps Planned 
We are moving to **Phase 3**: PostgreSQL Database Implementation.
The target is creating the table schema, setting up the `psycopg2` / `SQLAlchemy` connections, and safely writing the transformed data into the DB using UPSERT logic (`ON CONFLICT (station_id, ts) DO UPDATE`).
# Original Project Context & Requirements

*This document preserves the exact original architectural context, rules, and boundaries established for the Air Quality Risk Forecasting system.*

## 1. PROJECT OBJECTIVE
The project is an end-to-end air-quality risk forecasting system built using real government air-quality data from India.
The system is intended to demonstrate a serious data-science/data-engineering workflow rather than simply training a model.
The broad lifecycle is:
RAW GOVERNMENT DATA ↓ DATA PROFILING ↓ DATABASE DESIGN ↓ ETL / DATA CLEANING ↓ POSTGRESQL CURATED DATA ↓ DATA VALIDATION ↓ EDA ↓ FEATURE ENGINEERING ↓ AQI FORECASTING ↓ RISK CLASSIFICATION ↓ CAUSAL / POLICY ANALYSIS ↓ DASHBOARD / DEPLOYMENT
The current project stage is: ETL validated → ERD/database design completed → PostgreSQL setup is next.

## 2. PRIMARY DATA SOURCE
A. **CAAQMS raw data**: PRIMARY raw measurement dataset. Row-oriented CSV format. 1-hour resolution.
B. **AQI Data Repository**: Target/reference data. XLSX wide/transposed structure where hour values appear as columns and `Date` values are day-of-month integers.

## 3. GEOGRAPHIC SCOPE
- **PRIMARY:** Delhi (7 specific stations).
- **SECONDARY:** Mumbai data exists locally, but it should NOT be mixed blindly into the primary Delhi analytical dataset. Mumbai is for external validation/comparison.

## 4. DATA PROFILING RESULTS
- 105 Delhi files, 21 CAAQMS CSV files, 84 AQI XLSX files.
- Missing values, timestamp anomalies, sentinel values, and varying schemas exist.

## 5. IMPORTANT DATA QUALITY DISCOVERIES
A. **Epoch timestamp problem:** AQI XLSX integer days parsed to 1970 UNIX epoch. Solved by extracting year/month from filename.
B. **Sentinel mistake:** Intial ETL dropped `9` and `-9`. They are legitimate measurements. Sentinels restricted to `-999`, `9999`, etc.
C. **Barometric pressure issue:** `bp_mmhg = 999` is an artifact/clip. Handled uniquely rather than globally. Range is actually in hPa (966-999).
D. **Invalid measurements:** Invalid values must NOT cause the entire hourly row to be deleted. Invalid field -> NULL, recorded in JSONB `qc_flags`, row preserved.
E. **Invalid timestamps:** Only fundamentally unrecoverable timestamps are dropped.

## 6. QC FLAG DESIGN
Unified `qc_flags` JSONB field in fact tables. 
Examples: `{"bp_mmhg": "OOB_999"}`. Nullifies invalid measurement, retains row, ensures auditability.

## 7. ETL ARCHITECTURE
Raw files are NEVER modified. Reproducible, idempotent, restartable. Source lineage preserved. Passed complete dry run.

## 8. FINAL DRY-RUN RESULTS
- 112 total files (inc. Mumbai). 162,096 CAAQMS records, 59,717 AQI records.
- 0 invalid TS remaining, 930 out-of-bound nullifications, 0 sentinel replacements.

## 9. DATABASE DESIGN
Four CORE tables: `stations`, `source_files`, `caaqms_hourly`, `aqi_hourly`.
Analytical/ML tables are intentionally NOT part of current ingestion.

## 10. STATIONS TABLE
Dimension table. Canonical names. Raw folder naming remains traceable (e.g. keeping Jahangirpuri trailing tab mapping).

## 11. SOURCE_FILES TABLE
Data lineage. `source_file_id` is its own PRIMARY KEY. Every curated observation traces back here.

## 12. CAAQMS_HOURLY TABLE
Curated hourly measurements. Constraint: `UNIQUE(station_id, timestamp)`.

## 13. AQI_HOURLY TABLE
Curated hourly AQI observations. Constraint: `UNIQUE(station_id, timestamp)`.

## 14. TIMEZONE
Use `Asia/Kolkata` for source timestamps. PostgreSQL MUST use timezone-aware `TIMESTAMPTZ`.

## 15. INDEXING
Index `station_id`, `ts`, `(station_id, ts)`. 

## 16. DATABASE NORMALIZATION PRINCIPLE
Maintain normalization. Use foreign keys. Keep raw/curated separate from analytical features.

## 17-20. ML / RISK / EDA / CAUSAL LATER (FUTURE)
Supervised learning, lag features (1h, 6h, etc.) are for AFTER the DB is loaded. Risk classes (false alarms, precision/recall) and interventions (GRAP, stubble-burning) are future phases.

## 21. CURRENT RAW DATA DIRECTORY
`Og Data/Delhi data`. Do not move, do not rename, do not assume filename patterns blindly.

## 22-25. POSTGRESQL IMPLEMENTATION REQUIREMENTS
Prefer reproducible local setup. Use env vars for credentials, not hard-coded files. Support idempotent ingestion using Constraints. Make ETL loader safe to rerun. Prioritize traceability and idempotency over speed. Build migration scripts.
# Air Quality Risk Forecasting - Technical Timeline

*A chronological log of engineering, data science, and architectural milestones.*

## Phase 1: Project Initialization & Exploratory Data Analysis (EDA)
- **Objective:** Provision the repository, map the raw data structures, and define the ETL schema.
- **Milestones:**
  - Ingested raw datasets spanning two architectures: 
    - Delhi: High-resolution CAAQMS univariate pollutant CSVs (24 dims, ~8760 rows/year/station, 2023-2026).
    - Mumbai/Delhi: Wide-format localized AQI Excel reports (Jan-Jul 2026).
  - Identified data structural inconsistencies: `Jahangirpuri` trailing tab (`\t`) artifact in directories; Missing values coded as string `"NA"`.
  - Defined Canonical DB Schema mapping 24 raw CSV headers to normalized snake_case identifiers (e.g., `PM2.5 (µg/m³)` -> `pm25`).

## Phase 2: ETL Pipeline Development & Hardening (Completed)
- **Objective:** Build a reproducible, dry-run-capable ETL pipeline with strict validation constraints and metadata output.
- **Milestones:**
  - Constructed unified schema mapping, physical bounds validation bounds (`etl/schemas.py`), and robust validation engines (`etl/validation.py`).
  - **Critical Bug Fix 1 (Timestamp Epochs):** Discovered AQI XLSX `Date` columns stored day-of-month integers, which `pd.to_datetime` coerced into `1970-01-01` epoch, dropping 100% of data. Fixed via regex metadata extraction from filenames (`r"_(20\d{2})_([A-Za-z]+)_"`) combined dynamically with localized IST conversions (`dt.tz_localize("Asia/Kolkata")`).
  - **Critical Bug Fix 2 (Sentinel Overlap):** Validated that integer sentinels `9` and `-9` were triggering massive false positives in legitimate environmental variables (e.g., 9°C, 9µg/m³). Constrained sentinels to `{-9999, 9999, -999}`.
  - **Critical Bug Fix 3 (Physical Bounds):** Corrected `bp_mmhg` physical domain ceiling to `998.9` after recognizing data distribution was reported in hPa (966-999) rather than mmHg, isolating just the `999.0` sensor clip anomaly without nullifying historical readings.
  - **QC Metadata Logging:** Introduced row-level `{col: status}` JSON logs stored in a `qc_flags` column for non-destructive data auditing, isolating failures to cells rather than sweeping entire rows.
  - **Execution:** Successfully processed 112 files yielding 162,096 CAAQMS rows and 59,717 AQI rows with 0 unhandled epoch failures. 

## Phase 3: Database Implementation (Upcoming)
- **Objective:** Map the validated ETL output into a physical PostgreSQL schema.
- **Milestones:**
  - Define `CREATE TABLE` architectures.
  - Implement Idempotent ingest sequences (`ON CONFLICT (station_id, ts) DO UPDATE`).
  - Migrate ETL pipeline from dry-run metrics to staging/production commits.

## Phase 4: Feature Engineering & Modeling (Planned)
- **Objective:** Temporal aggregations, rolling window features, and predictive modeling for Risk Forecasting.
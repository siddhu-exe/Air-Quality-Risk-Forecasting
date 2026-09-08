# Technical Timeline

*A chronological log of engineering, data science, and architectural milestones.*

## Phase 1: Project Initialization & Exploratory Data Analysis (EDA)
- **Objective:** Provision the repository, map the raw data structures, and define the ETL schema.
- **Milestones:**
  - Evaluated primary CAAQMS tall CSV formats vs localized AQI transposed XLSX architectures.
  - Profiled schema divergence, time-series gaps, missingness rates, and variable string inconsistencies.
  - Defined the strict boundary: Mumbai data shall exist strictly for external validation and secondary comparison, separate from the primary Delhi modeling target.

## Phase 2: ETL Pipeline Development & Hardening (Completed)
- **Objective:** Build a reproducible, dry-run-capable ETL pipeline with strict validation constraints and metadata output.
- **Milestones:**
  - **Epoch Bug Fix:** Uncovered that AQI integer-dates coerced to 1970 UNIX epochs; implemented robust metadata regex extraction off filenames to dynamically reconstruct localized `Asia/Kolkata` timeframes.
  - **Sentinel Overlap Correction:** Proved that baseline values (e.g. `9`, `-9`) were authentic measurements incorrectly pruned. Redefined hard bounds to strict extremes (`-999`, `9999`).
  - **Variable-Specific Boundaries:** Trapped `999.0` sensor-clips natively inside `bp_mmhg` configuration to preserve overarching hPa (966-999) atmospheric variance.
  - **Non-Destructive Metadata (JSONB):** Architected robust row retention—bad metrics nullify the particular cell and output a detailed warning string to the `qc_flags` dictionary field to maintain continuous hourly records.
  - **Dry-Run Validated Baseline:** 162,096 CAAQMS + 59,717 AQI observations; 0 epoch drops, 930 precise QC hits.

## Phase 3: Database Implementation (CURRENT)
- **Objective:** Map the validated ETL output into an idempotent physical PostgreSQL paradigm without leaking ML components prematurely.
- **Milestones:**
  - Enforce Normalized dimension layer (`stations` table) separate from lineage telemetry (`source_files`).
  - Implement two localized Fact tables: `caaqms_hourly` (pollutants) + `aqi_hourly` (target index).
  - Implement strict unique temporal constraints `UNIQUE(station_id, timestamp)` to pave the way for `ON CONFLICT DO UPDATE` operations, guaranteeing zero duplication upon multiple sequential runs.
  - Execute PostgreSQL SQL migrations natively.
  - **Infrastructure WIN:** Bypassed intensive Docker containerization entirely. Bootstrapped a purely local, user-space, zero-root PostgreSQL cluster (`initdb`) in `local_pg_data/` operating on port 5433 to maximize computational efficiency for laptop development.

## Phase 4: Feature Engineering & Forecasting (Scheduled)
- **Objective:** Supervised learning and risk categorization.
- **Milestones:**
  - Execute predictive pipelines integrating temporal lags, localized weather causality matrices, and AQI variance outputs.
  - Establish exact forecast horizons (1H/6H/24H/etc.) scaling into categorical risk brackets (cost-aware classification mappings).
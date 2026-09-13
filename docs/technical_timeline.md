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

## Phase 3: Database Implementation & Production Ingestion (Completed)
- **Objective:** Map the validated ETL output into an idempotent physical PostgreSQL paradigm without leaking ML components prematurely.
- **Milestones:**
  - Enforced Normalized dimension layer (`stations` table) separate from lineage telemetry (`source_files`).
  - Implemented two localized Fact tables: `caaqms_hourly` (pollutants) + `aqi_hourly` (target index).
  - Implemented strict unique temporal constraints `UNIQUE(station_id, timestamp)` with `ON CONFLICT DO UPDATE` operations, guaranteeing zero duplication upon multiple sequential runs.
  - Executed PostgreSQL SQL migrations natively with `ON DELETE RESTRICT` FK constraints.
  - **Infrastructure WIN:** Bypassed intensive Docker containerization entirely. Bootstrapped a purely local, user-space, zero-root PostgreSQL cluster (`initdb`) in `local_pg_data/` operating on port 5433 to maximize computational efficiency for laptop development.
  - **Production Load Success:** Ingested 105 Delhi source files, populating 162,096 `caaqms_hourly` observations and 57,946 `aqi_hourly` records with zero data loss and full auditability.

## Phase 4: Exploratory Data Analysis & Statistical Profiling (Completed)
- **Objective:** Deep, multi-dimensional, read-only SQL-first exploration of database records, uncovering temporal, spatial, and multi-pollutant structures without leaking forecasting models.
- **Milestones:**
  - Built SQL analytical pipeline using CTEs, `PERCENTILE_CONT`, `EXTRACT` (Hour/Month/DOW), window `LAG()` functions, and `CORR()` / `REGR_SLOPE()` directly against Postgres on port 5433.
  - **Spatial Synchronization:** Quantified regional macro-forcing across Delhi with cross-station Pearson correlation $r \ge 0.92$ for AQI and $r \ge 0.84$ for PM2.5.
  - **Diurnal Atmospheric Dynamics:** Identified bimodal PM2.5 peaks at 07:00 and 23:00 (~155 µg/m³), midday photochemical O3 peak at 14:00 (~37–45 µg/m³), and 24h buffered AQI rolling behavior.
  - **Autoregressive Horizons:** Measured lag persistence from lag-1 ($r = 0.998$ for AQI, $r = 0.956$ for PM2.5) out to lag-168 (1 week), discovering 24-hour diurnal harmonic rebound ($r = 0.748$).
  - **Extreme Episodes:** Tracked 123 discrete severe pollution episodes (AQI $\ge 400$ for $\ge 6$h), with the longest spanning 405 continuous hours at Bawana.
  - **Meteorological Usability:** Validated Temperature ($r = -0.521$), Relative Humidity ($r = +0.272$), Wind Speed ($r = -0.158$, Spearman $\rho = -0.292$), and Solar Radiation ($r = -0.157$) for downstream models; excluded 100% missing Xylene and 56.6% missing Rainfall.
  - **Deliverables:** Generated 11-figure visual suite in `reports/eda/figures/`, comprehensive 12-section empirical report `reports/eda/EDA_REPORT.md`, summary CSVs in `reports/eda/`, and passed formal Gate Verdict to Phase 5.

## Phase 5: Feature Engineering & Baseline Modelling (Current / Next)
- **Objective:** Construct tabular feature matrices and train baseline/ML forecasting models for multi-horizon PM2.5 and AQI prediction.
- **Milestones:**
  - Build feature extraction pipelines (`src/features/`): temporal lags (1–168h), rolling window aggregates (6h/24h mean/std/min/max), cyclical time encodings (sine/cosine for hour/month), and cross-station spatial neighbor features.
  - Implement heuristic baselines (`src/models/`): Naive Persistence ($AQI(t) \approx AQI(t-1)$), 24h Seasonal Persistence, Rolling Climatological Mean.
  - Implement supervised ML models: Ridge/Lasso, Random Forest, LightGBM/XGBoost for 1h, 6h, 12h, and 24h ahead forecasting.
  - Evaluate against RMSE, MAE, and directional accuracy metrics.

## Phase 6+: Risk Classification, Causal Analysis, & Deployment (Scheduled)
- **Objective:** Convert forecasts into action-oriented health risk categories and decision-support tools.
- **Milestones:**
  - Map forecasts to CPCB AQI risk bands (Severe, Very Poor, Poor, Moderate, Satisfactory, Good).
  - Cost-sensitive classification optimizing for low false-alarm rates during high-risk winter episodes (GRAP intervention trigger thresholds).
  - Causal/policy analysis and lightweight interactive monitoring dashboard.
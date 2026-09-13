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

## Phase 5: Feature Engineering & Baseline Modelling (Completed)
- **Objective:** Construct a leakage-safe tabular feature matrix across 7 feature groups, audit future forecasting targets ($h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$), evaluate benchmark baselines across chronological partitions, and rank feature predictive power.
- **Milestones:**
  - **Forecasting Target Definition & Audit:** Formalized lead targets $\text{AQI}(t+h)$ for 1h, 6h, and 24h horizons; confirmed high target availability (>99.2% for 1h, >98.3% for 6h, >96.2% for 24h) across 57,946 ground-truth records.
  - **7-Group Feature Engineering Taxonomy:** Engineered 124 causal features spanning Recent AQI Lags (10), Multi-Pollutant Lags (35), Causal Trailing Rolling Stats (32), Temporal/Cyclical Encodings (13), IMD Seasonality (4), Usable Meteorology (24), and Spatial Network Signals (6).
  - **Mathematical Leakage Audit:** Enforced trailing rolling windows $[t-W+1, t]$, positive lag shifts, leave-one-out spatial aggregation on $t-1$ observations, and 2024 historical warm-up buffer preservation to prevent cold-start boundary truncation.
  - **Chronological 3-Way Partitioning:** Enforced non-overlapping splits: Train (Jan–Aug 2025, 67%), Validation (Sep–Oct 2025, 16.5%), and Test (Nov–Dec 2025, 16.5% - Peak Winter Crisis).
  - **Baseline Benchmarking:** Evaluated Naive Persistence, 24h Seasonal Persistence, and 24h Moving Average baselines; discovered near-perfect persistence at 1h ($\text{MAE} \approx 2.40$), moderate degradation at 6h ($\text{MAE} \approx 12.72$), and total persistence collapse at 24h on the Winter test set ($\text{MAE} \approx 38.34, R^2 \approx 0.1848$).
  - **Feature Ranking & Group Importance:** Quantified Pearson correlations across all 124 features, establishing that Group A (AQI Lags), Group G (Cross-Station Spatial), and Group C (Rolling Stats) carry highest predictive power, with Meteorology (Group F) and Seasonality (Group E) providing essential long-range variance.
  - **Hardware & CPU Optimization:** Optimized pipeline with vectorized Pandas operations (under 2.5s execution) and compact Snappy Parquet storage (`data/processed/features_2025.parquet`).
  - **Deliverables:** Structured specifications in `phase_5/`, baseline records in `reports/modeling/baselines.csv`, feature rankings in `reports/modeling/feature_importance.csv`, and comprehensive report `reports/modeling/PHASE_5_BASELINE_REPORT.md`.

## Phase 6: Advanced Model Development & Optimization (Current / Next)
- **Objective:** Develop, optimize, and evaluate supervised forecasting models (Gradient Boosting, LightGBM, Random Forest, Ridge) across multi-horizon AQI and PM2.5 targets.
- **Milestones:**
  - Train and tune multi-station regression models for 1h, 6h, and 24h forecasting horizons.
  - Execute hyperparameter optimization and feature subset ablations.
  - Evaluate against RMSE, MAE, MAPE, directional accuracy, and extreme episode error ($\text{AQI} \ge 300$).
  - Export trained model artifacts and validation prediction matrices.

## Phase 7+: Risk Classification, Causal Analysis, & Deployment (Scheduled)
- **Objective:** Convert forecasts into action-oriented health risk categories and decision-support tools.
- **Milestones:**
  - Map forecasts to CPCB AQI risk bands (Severe, Very Poor, Poor, Moderate, Satisfactory, Good).
  - Cost-sensitive classification optimizing for low false-alarm rates during high-risk winter episodes (GRAP intervention trigger thresholds).
  - Causal/policy analysis and lightweight interactive monitoring dashboard.
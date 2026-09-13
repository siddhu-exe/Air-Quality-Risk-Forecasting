# LLM Context: Project Architecture & State

**Purpose:** Read this file to instantly understand the repository structure, previous bug fixes, constraints, and current state of the Air Quality Risk Forecasting system. Do not change project direction or introduce ML technologies prematurely.

## Project Scope & Lifecycle
**Lifecycle Pipeline:** RAW GOVERNMENT DATA -> DATA PROFILING -> DATABASE DESIGN -> ETL/DATA CLEANING -> POSTGRESQL -> DATA VALIDATION -> EDA -> FEATURE ENGINEERING -> BASELINE BENCHMARKING -> AQI FORECASTING -> RISK CLASSIFICATION -> CAUSAL/POLICY ANALYSIS -> DASHBOARD.
**Current Stage:** Phase 3 (DB Ingestion) Completed -> Phase 4 (EDA) Completed -> Phase 5 (Feature Engineering & Baseline Benchmarking) Completed -> **Moving to Phase 6 (Advanced Model Training & Multi-Horizon Forecasting)**.

## Geographic Scope
- **Primary:** Delhi (7 specific stations: Anand Vihar, Bawana, Dwarka-Sector 8, ITO, Jahangirpuri, Punjabi Bagh, R K Puram).
- **Secondary:** Mumbai data exists but MUST NOT be mixed into the primary Delhi dataset blindly. It is reserved for external validation later.

## Database ERD & Production State (Phase 3 Completed)
The PostgreSQL schema strictly implements **4 Core Tables** in a native user-space cluster (port 5433):
1. `stations`: Dimension table (7 canonical stations).
2. `source_files`: Lineage tracking (105 source files ingested).
3. `caaqms_hourly`: Hourly pollutants (PM2.5, PM10, NOx, Ozone, etc.) and weather (Temp, RH, WS, etc.) totaling **162,096** rows.
4. `aqi_hourly`: Target metric tracking totaling **57,946** rows.
*Constraints & Idempotency:* `UNIQUE(station_id, timestamp)` on fact tables for idempotent `ON CONFLICT DO UPDATE` loads. Foreign keys hardened with `ON DELETE RESTRICT`. Uses `TIMESTAMPTZ` set to `Asia/Kolkata`.

## Critical Data/ETL Bugs Solved (Must Maintain!)
1. **Epoch Bug Avoided:** AQI XLSX `Date` columns contain bare integers (1, 2...). We extract `YYYY-Month` from the filename using regex and concatenate it with the integer to reconstruct the exact `Asia/Kolkata` timestamp.
2. **Sentinel False Positives:** Values `9` and `-9` were triggering valid readings to nullify (e.g. 9°C). Sentinels are strictly bounded to extreme structural constants (`-999`, `-9999`, `9999`).
3. **Barometric Pressure Bounds:** `bp_mmhg=999.0` is an explicit physical clip error. Validation traps `bp_mmhg` bounded at `(400, 998.9)` to save genuine hPa scale readings (966-999).
4. **Invalid Measurement Row Retention:** A bad measurement nullifies the specific cell, NOT the row. The row remains, and a JSON log (e.g. `{"pm25": "SENTINEL_-999"}`) is stamped onto the row's `qc_flags` JSONB column.

## Phase 4 (EDA) Key Findings & Statistical Discoveries
1. **Airshed Spatial Synchronization:** Pairwise cross-station Pearson correlation across all 7 Delhi stations is $r \ge 0.92$ for AQI and $r \ge 0.84$ for PM2.5. Delhi behaves as a regionally synchronized airshed under macro-scale atmospheric forcing.
2. **Diurnal Atmospheric Decoupling:** 
   - **PM2.5:** Sharp bimodal cycle peaking at 07:00 and 23:00 (~155 µg/m³) due to traffic rush hours and planetary boundary layer (PBL) compression.
   - **O3:** Single photochemical afternoon peak at 14:00 (~37-45 µg/m³) driven by solar radiation.
   - **AQI:** Buffered 24-hour moving average with a flattened diurnal curve.
3. **Autoregressive Persistence:**
   - AQI lag-1 persistence is near-unity ($r \approx 0.998$) and remains high at 1-week lag ($r \approx 0.77$).
   - PM2.5 has strong short-term persistence ($r \approx 0.956$ at lag-1), drops at lag-12 ($r \approx 0.610$), rebounds at the 24-hour diurnal harmonic ($r \approx 0.748$), and retains $r \approx 0.541$ at lag-168.
4. **Severe Pollution Episodes:** 123 discrete severe episodes (AQI $\ge 400$ for $\ge 6$ consecutive hours) identified, heavily concentrated in Winter (Nov-Jan).
5. **Meteorological Feature Usability:**
   - **High Usability:** Temperature ($r = -0.521$ with PM2.5), Relative Humidity ($r = +0.272$), Wind Speed ($r = -0.158$, Spearman $\rho = -0.292$), Solar Radiation ($r = -0.157$).
   - **Exclusions/Cautions:** Rainfall is sparse (56.6% missing); Xylene is 100% unpopulated; ITO station lacks meteorological sensors.
6. **Visual & Analytical Deliverables:** 11-figure visual suite in `reports/eda/figures/`, comprehensive report `reports/eda/EDA_REPORT.md`, and modular scripts in `src/eda/`. Gate passed to Phase 5.

## Phase 5 (Feature Engineering & Baselines) Key Findings
1. **Feature Taxonomy (124 Features):** Engineered 124 causal features across 7 groups: Group A (10 AQI lags), Group B (35 multi-pollutant lags), Group C (32 causal rolling stats), Group D (13 temporal/cyclical), Group E (4 season indicators), Group F (24 meteo features), Group G (6 spatial network signals).
2. **Strict Zero Leakage:** Enforced trailing windows $[t-W+1, t]$, positive lag offsets, and leave-one-out spatial network aggregates on $t-1$ observations. 2024 records used as warm-up buffer.
3. **Baseline Breakdown by Horizon:**
   - **1-Hour Horizon:** Naive Persistence achieves near-perfect tracking ($\text{MAE} \approx 2.40, R^2 \approx 0.995$) due to 24-hour moving buffer inertia in reported AQI.
   - **6-Hour Horizon:** Persistence degrades ($\text{MAE} \approx 12.72, R^2 \approx 0.902$).
   - **24-Hour Horizon:** Heuristic persistence collapses during winter test episodes ($\text{MAE} \approx 38.34, R^2 \approx 0.1848$), underscoring the necessity of multi-variate ML models with meteorology and spatial signals.
4. **Feature Predictive Ranking:** Group A (mean $|r| = 0.930$) and Group G (mean $|r| = 0.890$) dominate short-term correlation; Group F (Meteorology) and Group E (Seasonality) provide critical variance for 24h forecasts.
5. **Deliverables & Parquet Output:** 57,946 clean rows exported to `data/processed/features_2025.parquet`, baseline logs in `reports/modeling/baselines.csv`, and comprehensive report `reports/modeling/PHASE_5_BASELINE_REPORT.md`.

## Upcoming Phase 6 Roadmap (Advanced Model Training & Forecasting)
- **Models (`src/models/`):** Supervised gradient boosted trees (LightGBM, XGBoost), Random Forests, and regularized linear regressions trained for 1h, 6h, and 24h horizons across all 7 Delhi stations.
- **Optimization & Evaluation:** Hyperparameter tuning, feature ablation studies, MAPE, RMSE, MAE, and extreme episode error ($\text{AQI} \ge 300$).

## Infrastructure Requirements
- **NO DOCKER & NO GPU REQUIREMENT:** Lightweight, vectorized CPU computation only.
- **Database Engine:** We run a completely native, local, user-space PostgreSQL cluster via `initdb` stored securely inside `./local_pg_data` on port `5433`.
- **Start/Stop:** The environment is manually spun up via `pg_ctl -D local_pg_data start` to preserve battery and CPU when not actively ingesting data. 

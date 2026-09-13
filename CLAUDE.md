# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an evolving **air quality risk forecasting** project. It contains raw source data, an idempotent Python ETL pipeline backing a reliable PostgreSQL database schema, comprehensive Phase 4 EDA, and a fully completed Phase 5 Feature Engineering and Baseline Modeling suite. The project is currently transitioning to **Phase 6: Advanced Model Development & Multi-Horizon Forecasting**. The data covers two Indian cities:

- **Delhi**: Station-level hourly measurements from 7 DPCC/CPCB monitoring stations (2023–2026)
- **Mumbai**: City-level hourly AQI data (Jan–Jul 2026)

## Data Structure

```
Og Data/
├── Delhi data/
│   ├── Anand Vihar, Delhi - DPCC/
│   ├── Bawana, Delhi - DPCC/
│   ├── Dwarka-Sector 8, Delhi - DPCC/
│   ├── ITO, Delhi - CPCB/
│   ├── Jahangirpuri, Delhi - DPCC/   ← directory name has a trailing tab character
│   ├── Punjabi Bagh, Delhi - DPCC/
│   └── R K Puram, Delhi - DPCC/
│       ├── Raw Data/         ← CSV files, one per year (2023/2024/2025/2026)
│       └── AQI Hourly/       ← XLSX files, one per month (2025 full year)
└── Mumbai data/
    └── aqi_hourly_city_level__2026_<Month>_mumbai_2026.xlsx   ← city-level, XLSX only
```

## Data Formats

### Raw CSV (Delhi stations)
- Filename pattern: `{YEAR}_raw_data_hourly_{station}_1H.csv`
- 24 columns, 1-hour resolution, ~8760 rows/year
- Key columns: `Timestamp`, `PM2.5 (µg/m³)`, `PM10 (µg/m³)`, `NO`, `NO2`, `NOx`, `NH3`, `SO2`, `CO`, `Ozone`, `Benzene`, `Toluene`, `Xylene`, `O Xylene`, `Eth-Benzene`, `MP-Xylene`, `AT (°C)`, `RH (%)`, `WS (m/s)`, `WD (deg)`, `RF (mm)`, `TOT-RF (mm)`, `SR (W/mt2)`, `BP (mmHg)`, `VWS (m/s)`
- Missing values are represented as `NA` (not NaN/blank)
- Not all sensors are active at every station — expect columns populated with `NA` at some stations (e.g. ITO has no meteorological data; Dwarka has no Ozone)

### AQI Hourly XLSX (Delhi + Mumbai)
- Delhi: station-level, one file per month for 2025
- Mumbai: city-level aggregates, one file per month for Jan–Jul 2026

## Important Data Quirks

- The `Jahangirpuri` station directory has a **trailing tab character** in its name — use glob patterns or raw string paths carefully when scripting
- Delhi raw CSVs span 2023–2026 (Dwarka has 2023 data; others start 2024); 2026 files are partial (~5088 rows ≈ through late July)
- Mumbai has **no raw pollutant CSV** — only city-level AQI Excel files; the initial commit had a Bandra Kurla Complex CSV that was removed in commit `c400b02`
- Station operators: most Delhi stations are DPCC; ITO is CPCB — they may use different calibration standards

## Established Tech Stack & Data State
- Python: `pandas`, `numpy`, `scikit-learn`, `psycopg2`, `pyarrow`
- DB: PostgreSQL 16 hosted locally via `initdb` connecting on port 5433.
- Ingestion State: 105 total source files, >162K `caaqms_hourly` observations, and ~58K `aqi_hourly` logs.
- Processed Feature Matrix: `data/processed/features_2025.parquet` (57,946 rows, 130 columns, 124 causal features across 7 groups).
- Modeling Reports: `reports/modeling/baselines.csv`, `reports/modeling/feature_importance.csv`, `reports/modeling/PHASE_5_BASELINE_REPORT.md`.

## Completed Phases
- **Phase 1-3:** ETL Pipeline, Data Quality Hardening, Idempotent PostgreSQL Ingestion.
- **Phase 4:** Exploratory Data Analysis (EDA), Statistical Profiling, 11 Visualizations (`reports/eda/`).
- **Phase 5:** Feature Engineering & Baseline Modeling (124 causal features, leakage audit, heuristic baselines, feature ranking).

## Suggested Next Steps (Phase 6: Advanced Model Development & Forecasting)
We have successfully finished **Phase 5 (Feature Engineering & Baseline Modeling)**. The next stage is Phase 6:

1. Developing and tuning multi-station supervised regression models (Gradient Boosting, LightGBM, Random Forest, Ridge) across 1h, 6h, and 24h horizons.
2. Executing hyperparameter search, cross-station evaluations, and feature ablations.
3. Benchmarking against Phase 5 heuristic baselines on test-set metrics (MAE, RMSE, $R^2$, MAPE, Extreme Episode Error $\text{AQI} \ge 300$).
4. Exporting trained model artifacts and validation prediction matrices for downstream risk classification.

```
src/features/    # Feature construction from DB (124 features)
src/models/      # Baseline heuristics & ML forecasting architectures
phase_5/         # Phase 5 formal specifications & audits
models/          # Trained model artifacts / weights
reports/modeling/# Forecast baselines, feature importances, and evaluation reports
```

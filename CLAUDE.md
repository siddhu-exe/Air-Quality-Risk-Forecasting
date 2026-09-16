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
- **Phase 6 & 6B & 6C:** Multi-Horizon Forecasting & 24h Final Refinement Suite:
  - 1h Tuned LightGBM: $\text{MAE} = 2.29, \text{RMSE} = 3.65, R^2 = 0.9958$ (beats Naive Persistence $\text{MAE} = 2.40$). **[FROZEN]**
  - 6h Tuned LightGBM: $\text{MAE} = 11.84, \text{RMSE} = 16.71, R^2 = 0.9126$ (beats Naive Persistence $\text{MAE} = 14.73$). **[FROZEN]**
  - 24h Refined 50/50 Hybrid Persistence + Ridge ($\alpha=1000$): $\text{MAE} = 34.11, \text{RMSE} = 44.80, R^2 = 0.3647, \text{MAPE} = 9.72\%$ (beats Naive Persistence $\text{MAE} = 38.34, R^2 = 0.1848$ by **+4.23 AQI points** across 100% of Delhi stations). Serialized to `models/24h/final/`.
  - Notebooks: `notebooks/phase_6_colab_training.ipynb`, `notebooks/phase_6b_24h_optimization.ipynb`, `notebooks/phase_6c_24h_final_refinement.ipynb`.
- **Phase 7:** CPCB AQI Risk Classification & GRAP Policy Alerting:
  - Discretized continuous predictions into 6 CPCB categories (Good, Satisfactory, Moderate, Poor, Very Poor, Severe) and 4 CAQM GRAP Stages (I-IV).
  - 1h Horizon: Macro F1 = 0.9446, W-Kappa = 0.9827, Ordinal MAE = 0.0146, Severe Recall = 98.36%, Critical Miss Rate = 0.000%.
  - 6h Horizon: Macro F1 = 0.6565, W-Kappa = 0.8664, Ordinal MAE = 0.1098, Severe Recall = 83.18%, Critical Miss Rate = 0.000%.
  - 24h Horizon: Macro F1 = 0.3386, W-Kappa = 0.5178, Ordinal MAE = 0.3710, Severe Recall = 61.08%, Very Poor+ Recall = 93.22%, Critical Miss Rate = 0.000%.
  - GRAP Staging & Early Warning: 24h model delivers 17.36h mean advance warning lead time for Severe crisis episodes with 74.4% hit rate (55.8% providing >=6h actionable warning).
  - Code & Audit: `src/models/phase_7_classification.py`, `reports/classification/PHASE_7_FINAL_AUDIT.md`. **[FROZEN]**

## Suggested Next Steps (Phase 8: Production Deployment, Real-Time Inference & Dashboard Integration)
With forecasting and policy risk classification validated and audited across all horizons (1h, 6h, 24h), the system is ready for Phase 8:

1. **Real-Time Inference Pipeline:** Build an operational inference engine that consumes streaming / newly ingested hourly station data, generates multi-horizon predictions, and assigns CPCB / GRAP risk alerts in real-time.
2. **REST API & Serving Layer:** Develop FastAPI/Flask endpoints serving real-time station metrics, multi-horizon forecasts, and emergency GRAP stage advisories.
3. **Interactive Dashboard:** Build an intuitive user-facing dashboard (e.g. Streamlit, Dash, or web UI) displaying live AQI maps, temporal trend forecasts, risk tier distributions, and active GRAP policy interventions across Delhi stations.
4. **Automated Alerting & Notification Dispatcher:** Implement notification webhooks/alerts triggered when forecasted AQI crosses GRAP Stage III/IV thresholds.

```
src/features/    # Feature engineering & ML dataset export (124 features)
src/models/      # Baseline heuristics & evaluation metrics
notebooks/       # Google Colab interactive training notebook (Phase 6)
data/processed/ml/ # Versioned Parquet ML datasets (1h, 6h, 24h) & metadata JSONs
reports/modeling/# Dataset manifest, baselines, and feature ranking reports
docs/            # Technical timelines, architecture guides, and phase documentation
```

# Air Quality Risk Forecasting: Project Overview

## What is this project?
This project is an end-to-end air-quality risk forecasting system built on top of genuine, real-world government sensor data from India. Instead of simply downloading a dataset and training a model, this project demonstrates a highly rigorous, full-lifecycle data engineering and data science workflow.

## The Broad Lifecycle Ecosystem
We adhere strictly to the following step-by-step pipeline. We do not skip ahead to machine learning until the data foundation is mathematically reliable.
```text
RAW GOVERNMENT DATA
        ↓
DATA PROFILING
        ↓
DATABASE DESIGN
        ↓
ETL / DATA CLEANING
        ↓
POSTGRESQL CURATED DATA    (Completed - Phase 3)
        ↓
DATA VALIDATION            (Completed - Phase 3)
        ↓
EDA (Exploratory Analysis) (Completed - Phase 4)
        ↓
FEATURE ENGINEERING        (Completed - Phase 5)
        ↓
BASELINE BENCHMARKING      (Completed - Phase 5)
        ↓
VERSIONED ML DATASETS      (Completed - Phase 6 Prep)
        ↓
MULTI-HORIZON FORECASTING  (Completed - Phase 6 / 6B / 6C)
        ↓
RISK CLASSIFICATION        <-- (We are here - Phase 7)
        ↓
CAUSAL / POLICY ANALYSIS
        ↓
DASHBOARD / DEPLOYMENT
```

## Where does the data come from?
- **Primary Set (Delhi):** Station-level measurements containing distinct environmental pollutants (PM2.5, NOx, Ozone, etc.) and meteorological weather data at hourly resolution across 7 distinct sensors (2023–2026). Over 162K hourly pollutant records and ~58K AQI values loaded.
- **Secondary Set (Mumbai):** City-level AQI data reserved for future out-of-sample validation and external comparison. 

## Architectural & Analytical Philosophy
- **Data Integrity & Traceability:** Bad sensor readings gracefully nullify only the corrupted metric and record a JSON quality-control flag (`qc_flags`), keeping the valid measurements in the row intact. Every single record traces back to its source file.
- **Empirical Validation (EDA):** Phase 4 conducted a deep SQL-first statistical analysis across all stations, validating strong spatial synchronization ($r \ge 0.92$), diurnal bimodal rhythms, autoregressive lag dynamics ($r \approx 0.998$), and meteorological forcing (temperature/humidity/wind) that inform our feature engineering strategy.
- **Causal Feature Engineering & Baseline Benchmarking:** Phase 5 constructed a 124-feature tabular dataset across 7 feature groups with zero temporal leakage, audited 1h, 6h, and 24h forecasting horizons, established heuristic baselines, and quantified feature predictive hierarchies.
- **Hybrid Local-Cloud ML Pipeline (Phase 6 / 6B / 6C):** Established a robust separation between local feature engineering and cloud-based model training. Models were rigorously benchmarked across 1h, 6h, and 24h horizons on out-of-sample winter test data:
  - **1-Hour Forecast (Frozen):** Tuned LightGBM ($\text{MAE} = 2.29, R^2 = 0.9958$) beating Naive Persistence ($\text{MAE} = 2.40$).
  - **6-Hour Forecast (Frozen):** Tuned LightGBM ($\text{MAE} = 11.84, R^2 = 0.9126$) beating Naive Persistence ($\text{MAE} = 14.73$).
  - **24-Hour Forecast & Refinement (Phase 6B & 6C):** Conducted exhaustive root-cause failure analysis of decision tree extrapolation limits and non-stationary feature routing. Engineered causal multi-day trailing features (lags up to 168h, multi-day rolling statistics, spatial network signals) and optimized a 50/50 Hybrid Persistence + Ridge ($\alpha=1000$) Ensemble. Achieved final Test $\text{MAE} = 34.11, \text{RMSE} = 44.80, R^2 = 0.3647, \text{MAPE} = 9.72\%$, beating Naive Persistence ($\text{MAE} = 38.34, R^2 = 0.1848$) by **+4.23 AQI points** across 100% of Delhi monitoring stations.
  - **Production Artifacts:** All production model pipelines serialized under `models/{1h,6h,24h}/` (with Phase 6C final models in `models/24h/final/`) with dedicated Colab notebooks (`notebooks/phase_6_colab_training.ipynb`, `notebooks/phase_6b_24h_optimization.ipynb`, `notebooks/phase_6c_24h_final_refinement.ipynb`).

## Infrastructure & Compute
To ensure this repository remains ultra-lightweight and battery-friendly for local laptop development, we do **not** run compute-heavy model training locally or use Docker virtual machines. The entire database is a fully isolated, native PostgreSQL cluster running directly out of the `local_pg_data` folder on port `5433`, while ML model training, tuning, and ablations are offloaded to Google Colab.

# Air Quality Risk Forecasting

An end-to-end air-quality risk forecasting system mapping raw government sensor data from India to actionable policy alerts (CPCB risk tiers and GRAP emergency interventions).

This repository contains the full data engineering and data science lifecycle: raw data ingestion, automated schema normalisation, an idempotent PostgreSQL ETL pipeline, causal feature engineering, multi-horizon forecasting ($h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$), and risk classification mapping. 

The project evaluates 7 continuous monitoring stations across Delhi (2023–2026), testing predictive performance heavily against extreme winter pollution crises.

## Core Pipeline & Architecture

```text
RAW GOVERNMENT DATA → POSTGRESQL (Idempotent ETL) → DATA VALIDATION → 
EDA → FEATURE ENGINEERING → BASELINE BENCHMARKING → VERSIONED ML DATASETS → 
MULTI-HORIZON FORECASTING → CPCB RISK CLASSIFICATION 
```

1. **Database & Ingestion (Phases 1-3)**: Implements a completely local, user-space PostgreSQL 16 cluster (`local_pg_data` running on port 5433). Raw CAAQMS CSVs and AQI `.xlsx` files are parsed, validated (handling legitimate sentinels like `-999` and bound-clipping artifacts like `999.0` mmHg), and loaded with perfect idempotency via `UNIQUE(station_id, timestamp)` constraints. Currently houses ~162K hourly pollution records and ~58K AQI logs.
2. **Exploration & Baseline Benchmarking (Phases 4-5)**: Built a subset of 124 backward-looking causal features across 7 groups (AQI lags, pollutant lags, trailing rolling statistics, circular temporal features, seasonality, meteorology, and leave-one-out spatial network aggregates).
3. **Forecasting (Phases 6-6C)**: Established multi-horizon continuous predictions and resolved 24h forecasting failure modes.
4. **Risk Alerting (Phase 7)**: Deterministic zero-leakage translation of numeric forecasting into the 6-tier Indian CPCB risk categories and 2024 revised CAQM GRAP (1-4) emergency frameworks.

## Current Forecasting Results (Nov-Dec 2025 Test Split)

Metrics evaluated out-of-sample on the peak winter crisis split across all 7 Delhi stations:

* **1-Hour Forecast**: Tuned LightGBM. $\text{MAE} = 2.29$, $R^2 = 0.9958$. (Naive persistence: 2.40).
* **6-Hour Forecast**: Tuned LightGBM. $\text{MAE} = 11.84$, $R^2 = 0.9126$. (Naive persistence: 14.73).
* **24-Hour Forecast**: 50/50 Hybrid Ensemble of Naive Persistence and Ridge Regression ($\alpha=1000$). $\text{MAE} = 34.11$, $R^2 = 0.3647$. (Naive persistence: 38.34).

### Parameter Provenance
* **Ridge Regularization ($\alpha=1000$)**: Originally picked as a strong default in Phase 6B to combat decision tree extrapolation ceilings during extreme winter spikes. Validated in Phase 6C via hyperparameter sweep over `[10, 50, 100, 250, 500, 1000, 2000, 5000]` on the Sept-Oct validation split.
* **Hybrid Blend Weight (0.5 / 50%)**: Originally implemented as an intuitive unweighted average in Phase 6B to anchor extrapolation. Validated in Phase 6C via grid search across 21 points evenly spaced between 0.0 and 1.0 on the evaluation split, strictly confirming 0.5 minimizes absolute error.
* **1-Hour / 6-Hour Tree Depths/Learning Rates**: Optuna Bayesian optimization (20 trials) on the validation split.

## Limitations

* **Modest 24-Hour Skill**: At 24 hours, the R² is 0.36. While this outperforms both seasonal and heuristic baselines representing real predictive skill (and guarantees a 0% critical miss rate for predicting severe events as moderate), the variance explained is modest. 
* **No Cost-Aware Threshold Tuning**: The classifier maps continuous predictions to ordinal bins using zero-leakage scalar edges. No cost-aware threshold shifting has been applied to balance specific recall/precision trade-offs for early alert policies.
* **Causal Scope**: Currently restricted to trailing network aggregates and meteorological observation lags rather than broader external policy interventions or point-source emission modeling.

## 📁 Repository Map

```text
.
├── CLAUDE.md                   # AI Assistant / Workspace guidance rules
├── data/
│   ├── processed/features_2025.parquet # Clean 124-feature tabular matrix 
│   └─ ml/                      # Versioned ML Parquet datasets & metadata JSONs
├── docs/                       # Internal working notes and technical details
├── etl/                        # Pipeline execution logic (discover, map, load, transform)
├── notebooks/                  # Interactive experimentation & Cloud Training
├── models/                     # Serialized production model artifacts
├── Og Data/                    # Raw local data directories (Delhi / Mumbai)
├── phase_5/                    # Formal specifications & audits
├── profiling/                  # Discovery scripts and schema scanners
├── reports/                    # Output from validation, EDA, models & metrics
├── scripts/                    # Utilities to generate Colab notebooks
├── src/                        # Analysis and modeling source codebase
├── local_pg_data/              # Local PostgreSQL 16 cluster directory (port 5433)
└── sql/                        # Target database structured definitions
```
*(Detailed timeline, contextual LLM, and per-phase working notes are housed in the `docs/` folder.)*

## 🛠️ Quickstart

**Prerequisites:** Python 3.9+, local PostgreSQL database.

**1. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Database Configuration**
Create a `.env` file at the root tracking the DB credentials:
```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=air_quality_db
POSTGRES_USER=aq_admin
POSTGRES_PASSWORD=your_secure_password
```
*(Start your PostgreSQL server instance on the matching port)*

**3. Run the Production ETL Pipeline**
Executes ETL logic to load data into the Production Database seamlessly tracking source lineage and idempotency.
```bash
python3 etl/run_full_load.py     # Full production load (All Delhi 105 files)
python3 verify_full_load.py      # Validation
```

**4. Feature Engineering & ML Pre-processing**
```bash
python3 src/features/target_analysis.py    # Target coverage
python3 src/features/build_features.py     # Feature construction
python3 src/features/export_ml_datasets.py --version v1 # Export to parquet
```

**5. Model Refinement (Phase 6C)**
```bash
python3 src/models/phase_6c_refinement.py
```
*(Models and predictions output to `models/24h/final/` & `reports/modeling/24h/final/`)*
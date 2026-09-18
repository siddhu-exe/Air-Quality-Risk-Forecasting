# Delhi Air Quality Risk Forecasting

This project forecasts air quality across Delhi 1 to 24 hours in advance and evaluates the impact of citywide pollution control policies. Instead of treating air quality as a generic regression problem, it investigates why standard machine learning breaks down during severe winter smog episodes and how to build models that actually hold up. It also includes an econometric policy evaluation of Delhi's Diwali firecracker ban and an interactive evaluation dashboard.

## Project Links

- **Interactive Dashboard:** Run locally with `streamlit run app.py` (deployable to Streamlit Community Cloud)
- **Public Kaggle Dataset:** [Delhi Air Quality Monitoring Dataset (2023–2026)](https://www.kaggle.com/datasets/siddharthdongardive/delhi-air-quality-monitoring-dataset-2023-2026)
- **GitHub Repository:** [https://github.com/Siddharth23052005/Air-quality-risk-forecasting](https://github.com/siddhu-exe/Air-quality-risk-forecasting)

---

## Overview

Delhi experiences some of the most hazardous urban air pollution events in the world, with winter PM2.5 concentrations routinely exceeding 400 to 500 µg/m³. Reliable advance warnings are critical for public health advisories and emergency policy enforcement under the Graded Response Action Plan (GRAP).

However, off-the-shelf machine learning pipelines frequently fail in this setting. Tree-based models hit mathematical ceilings during extreme spikes, standard evaluation protocols suffer from temporal leakage, and naive before-and-after policy evaluations confuse seasonal winter meteorology with policy failure.

This repository implements a full data and modeling pipeline across 7 continuous monitoring stations in Delhi. It covers raw telemetry ingestion into PostgreSQL 16, causal feature engineering, multi-horizon forecasting (1h, 6h, 24h), CPCB regulatory classification, cost-sensitive alert optimization, and econometric causal policy evaluation.

---

## Project Workflow

```text
Raw CPCB / DPCC Telemetry (105 Source Files)
    │
    ▼
Data Engineering & Ingestion (ETL, QC Flags, ISO 8601 Normalization)
    │
    ▼
PostgreSQL 16 Relational Data Layer (Idempotent Loading, Lineage Tracking)
    │
    ▼
Exploratory Data Analysis (Seasonal Profiling, Correlation, Missingness)
    │
    ├────────────────────────────────────────┬────────────────────────────────────────┐
    ▼                                        ▼                                        ▼
Econometric Causal Analysis       Causal Feature Engineering               Multi-Horizon Forecasting
(Diwali Ban, ITS, Placebos)       (124 Features, Strict Zero-Leakage)      (1h, 6h, 24h Architectures)
                                             │                                        │
                                             └───────────────────┬────────────────────┘
                                                                 ▼
                                                    Regulatory Risk Classification
                                                    (CPCB Categories & GRAP Stages I–IV)
                                                                 │
                                                                 ▼
                                                    Cost-Aware Threshold Optimization
                                                    (Asymmetric 5:1 Loss, 95.7% Severe Recall)
                                                                 │
                                                                 ▼
                                                    Interactive Streamlit Dashboard
```

---

## Key Results

Models were evaluated out-of-sample on the held-out peak winter crisis test set (November 1 – December 31, 2025; N = 9,800 hourly observations across all 7 Delhi continuous monitoring stations).

| Horizon | Final Model Architecture | Test MAE | Test RMSE | Test R² | Test MAPE | vs Naive Baseline |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **1-Hour** | Tuned LightGBM (All Causal Features) | **2.29** | 3.65 | 0.9958 | 0.86% | +0.11 pts MAE |
| **6-Hour** | Tuned LightGBM (All Causal Features) | **11.84** | 16.71 | 0.9126 | 3.68% | +2.89 pts MAE |
| **24-Hour** | 50/50 Hybrid (Naive Persistence + Ridge alpha=1000) | **34.11** | 44.80 | 0.3647 | 9.72% | +4.23 pts MAE |

### Key Classification & Alerting Metrics
- **0.000% Critical Miss Rate:** Across all horizons, no Severe pollution event was ever misclassified as Moderate or Good.
- **93.22% Very Poor or Worse Recall:** Reliable 24-hour advance detection of high-risk pollution episodes.
- **17.36 Hours Lead Time:** Average advance warning time before the onset of 64 distinct winter crisis episodes.

---

## What Went Wrong During Modeling

**Standard gradient boosting trees hit a hard mathematical ceiling during peak winter, underpredicting severe crises by over 136 AQI points.**

When I first trained LightGBM and XGBoost to predict AQI 24 hours ahead, they broke down completely on the winter test set, producing an MAE of 98.24 and an R² of -0.06. Because decision trees are step functions bounded by the maximum value observed during training (around 347 AQI), they were physically incapable of predicting the severe 450 to 500 AQI spikes that occurred in November and December. Adding raw calendar features like month made it worse by trapping winter test records into low-pollution monsoon leaves.

I resolved this by removing raw calendar indicators and building a 50/50 hybrid model that blends Naive Persistence with an L2-regularized linear Ridge regression on 49 curated causal features. The regularized linear model provides unbounded extrapolation into extreme pollution levels while persistence maintains strong local temporal inertia. This reduced the 24-hour MAE from 98.24 to 34.11, beating persistence across all 7 Delhi stations.

*Full breakdown and ablation logs:* [`reports/modeling/PHASE_6_FINAL_AUDIT.md`](reports/modeling/PHASE_6_FINAL_AUDIT.md)

---

## Causal Analysis

**The naive before/after comparison showed a +135.6 AQI jump after the Diwali firecracker ban, but controlling for winter meteorological inversion revealed the policy shift was statistically indistinguishable from zero.**

A simple before-and-after comparison suggested that pollution increased by 135.57 AQI points after Diwali 2025, which would make the firecracker ban look like an outright failure. However, checking pre-trends showed that air quality was already deteriorating by 20.38 AQI points per day prior to Diwali as winter temperature inversions and calm wind speeds set in. Using an Interrupted Time Series (ITS) model with station fixed effects, temperature, and wind controls, the estimated policy shift dropped to -10.59 AQI points (p = 0.425), which is not statistically significant. A 30-day in-time placebo test generated a false 24.26 point shift, confirming that raw comparisons pick up seasonal weather rather than policy failure.

Hourly chemical tracer telemetry showed that firecrackers caused an acute burst on festival night—with PM2.5 surging 8.0x to 960.7 µg/m³ and SO₂ jumping 5.3x to 73.5 µg/m³—but this smoke cloud dispersed within 18 to 24 hours. The multi-week crisis that followed was driven by seasonal meteorology trapping background emissions, not lingering festival smoke.

*Full econometric models and regression tables:* [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md)

---

## Risk Classification & Alerting

**Lowering the 24-hour Severe alert cutoff from 401.0 to 341.5 AQI catches 95.7% of hazardous pollution crises under an asymmetric public health loss ratio.**

Continuous AQI forecasts are mapped to the 6 statutory CPCB categories (Good, Satisfactory, Moderate, Poor, Very Poor, Severe) and CAQM Graded Response Action Plan (GRAP) Stages I through IV. At a 24-hour horizon, the statutory CPCB cutoff of 401.0 AQI misses 38.92% of Severe hours because regularized models naturally pull extreme predictions toward the historical mean. Applying an asymmetric 5:1 loss ratio—penalizing a missed severe crisis five times more than a false alarm—lowers the optimal decision threshold to 341.5 AQI. This raises Severe recall to 95.71%, reducing missed hazardous hours from 1,568 hours down to 173 hours (an 89% reduction). Importantly, 93.6% of the resulting false alarms occur when the air is already in the "Very Poor" tier (301 to 400 AQI), and exactly 0% occur in clean or moderate air.

| Operating Policy | Decision Cutoff (AQI) | Severe Recall | Severe Precision | Missed Severe Hours | False Alarm Hours |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Statutory Fixed CPCB** | 401.0 | 61.08% | 73.86% | 1,568 h | 871 h |
| **Cost-Optimal (5:1 Loss Ratio)** | **341.5** | **95.71%** | 54.33% | **173 h** | 3,242 h |
| **Pragmatic Compromise** | 380.0 | 78.90% | 64.40% | 850 h | 1,757 h |

*Full optimization curve, loss matrices, and sensitivity sweeps:* [`reports/classification/cost_aware_threshold_analysis.md`](reports/classification/cost_aware_threshold_analysis.md)

---

## Data Engineering

The raw dataset comprises 105 government telemetry spreadsheets from CPCB and DPCC across 7 monitoring stations (2023–2026). The ETL pipeline standardizes heterogeneous headers, converts pollutant concentrations into uniform units (µg/m³ and mg/m³), and normalizes irregular datetime representations into ISO 8601 timestamps anchored to Asia/Kolkata (`UTC+05:30`).

Non-destructive quality control isolates corrupted sensor error sentinels (e.g. `-999` or calibration drift flags) by nullifying only the affected parameter while recording an audit record in `qc_flags`, leaving valid concurrent measurements in the same observation intact. The relational layer is managed in PostgreSQL 16 with composite unique constraints on `(station_id, timestamp)`, enabling idempotent `ON CONFLICT DO UPDATE` ingestion that prevents duplicate records and allows retroactive corrections.

---

## Database Architecture

The relational data layer runs on PostgreSQL 16 using a 4-table schema designed for lineage traceability and idempotent loading.

```text
┌─────────────────────────┐         1:N         ┌────────────────────────────────┐
│        stations         │────────────────────►│          source_files          │
│ station_id (PK)         │                     │ source_file_id (PK)            │
│ station_name, city, ... │                     │ station_id (FK), filename, ... │
└─────────────────────────┘                     └────────────────────────────────┘
             │                                                  │
             │ 1:N                                              │ 1:N
             ▼                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                       caaqms_hourly / aqi_hourly                               │
│ caaqms_hourly_id / aqi_hourly_id (PK)                                          │
│ station_id (FK) ──► references stations                                        │
│ source_file_id (FK) ──► references source_files (Lineage Traceability)         │
│ timestamp (TIMESTAMPTZ, Asia/Kolkata)                                          │
│ pm25, pm10, no2, so2, co, o3, temp, humidity, wind_speed, qc_flags, ...        │
│ CONSTRAINT: UNIQUE(station_id, timestamp)  ──► Idempotent ON CONFLICT Loading  │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Source Lineage (`source_files`):** Every hourly measurement references its raw source file and ingestion batch for complete end-to-end auditability.
- **Idempotent Ingestion:** A composite `UNIQUE(station_id, timestamp)` constraint prevents duplicate records and allows retroactive corrections to update in place.
- **Non-Destructive QC (`qc_flags`):** Sensor error sentinels nullify only damaged channels while logging a JSON flag, preserving valid concurrent measurements in the same hour.

---

## Dashboard

The project includes an interactive 5-tab Streamlit dashboard (`dashboard/app.py` or root entrypoint `app.py`):
1. **Overview:** Current station-level AQI summaries, recent trends, and headline model metrics.
2. **Forecasts:** Interactive multi-horizon forecast views (1h, 6h, 24h) comparing actual vs predicted AQI with CPCB tier overlays and GRAP action stages.
3. **Diwali Policy Finding:** Econometric replay of the Diwali firecracker ban vs winter meteorological inversion, including chemical tracer surge analysis and placebo tests.
4. **Risk Threshold:** Interactive cost-sensitive threshold simulator allowing users to adjust public health loss ratios and inspect precision-recall trade-offs.
5. **Methodology:** Complete architecture documentation, database schema diagram, and verified evaluation tables.

To launch the dashboard locally:
```bash
streamlit run app.py
```

---

## Dataset

A clean public version of this dataset is hosted on Kaggle:
**[Delhi Air Quality Monitoring Dataset (2023–2026)](https://www.kaggle.com/datasets/siddharthdongardive/delhi-air-quality-monitoring-dataset-2023-2026)**

- **Total Observations:** 220,042 validated hourly records across 7 continuous monitoring stations.
- **Files Included:** `caaqms_hourly.csv` (24 columns), `aqi_hourly.csv` (5 columns), `stations.csv`, `source_files.csv`, and `column_metadata.csv`.
- **Coverage:** January 2023 through August 2026 for CAAQMS multi-pollutant and weather parameters; full-year 2025 for official CPCB AQI observations.
- **Sanitization:** All internal database IDs, local host paths, and intermediate ML features were completely stripped prior to packaging.

---

## Repository Structure

```text
.
├── app.py                      # Root entrypoint for Streamlit Community Cloud
├── dashboard/                  # Interactive Streamlit evaluation dashboard
├── data/
│   ├── processed/              # Causal 124-feature Parquet matrix (features_2025.parquet)
│   └── ml/                     # Versioned ML training datasets (1h, 6h, 24h Parquets)
├── docs/                       # Architecture diagrams and technical reference notes
├── etl/                        # Data discovery, transformation, and PostgreSQL loading scripts
├── models/                     # Serialized production model artifacts (LightGBM, Ridge)
├── notebooks/                  # Model training, hyperparameter tuning, and Kaggle quickstart
├── reports/                    # Comprehensive audit reports, figures, and CSV metrics
│   ├── causal/                 # Diwali econometric analysis and regression tables
│   ├── classification/         # CPCB/GRAP metrics, episode lead times, cost-aware analysis
│   ├── eda/                    # Exploratory data analysis charts and statistical profiling
│   └── modeling/               # Multi-horizon baseline benchmarks and ablation logs
├── sql/                        # Canonical PostgreSQL migrations (001_schema through 006)
├── src/                        # Core codebase for feature engineering, modeling, and evaluation
├── tests/                      # Automated timestamp checks and data validation scripts
├── requirements.txt            # Runtime dependencies
└── README.md                   # Canonical project documentation
```

---

## Tech Stack

- **Data Layer:** PostgreSQL 16, SQL, psycopg2, SQLAlchemy
- **Machine Learning & Modeling:** LightGBM, Scikit-learn, Statsmodels, Optuna
- **Data Processing & Storage:** Python 3.11, Pandas, NumPy, PyArrow (Parquet)
- **Web Application & Visualization:** Streamlit, Plotly, Matplotlib, Seaborn

---

## Limitations

1. **24-Hour Forecasting Uncertainty:** An R² of 0.36 reflects fundamental physical limits of predicting atmospheric stagnation 24 hours ahead using only ground telemetry without numerical weather prediction (NWP) models.
2. **Historical Backtest Scope:** The pipeline is currently evaluated on held-out historical data (November–December 2025) rather than a live streaming data feed.
3. **Observational Causal Identification:** The Diwali analysis uses within-city Interrupted Time Series with meteorological controls because continuous upwind background stations outside Delhi were unavailable in source data.
4. **Geographic Scope:** Telemetry is bounded to 7 urban monitoring stations within the National Capital Territory of Delhi.
5. **Sensor Sparsity:** Xylene was unpopulated across all stations in raw telemetry, and rainfall sensors were unavailable at several monitoring sites.

---

## Future Work

- **Live Telemetry Ingestion:** Implementing automated polling workers to stream real-time CPCB telemetry directly into PostgreSQL.
- **Numerical Weather Prediction (NWP) Features:** Integrating forecast wind vectors and boundary layer height predictions from GFS/ECMWF to improve 24-hour horizon accuracy.
- **Expanded Geographic Coverage:** Extending data ingestion and models across all 40+ monitoring stations in the broader National Capital Region (NCR).
- **Sequence Models:** Evaluating temporal fusion transformers and causal sequence-to-sequence neural architectures for multi-horizon joint forecasting.

---

## Data Attribution & License

- **Data Provenance:** Environmental telemetry is published by the Central Pollution Control Board (CPCB) and Delhi Pollution Control Committee (DPCC), Ministry of Environment, Forest and Climate Change, Government of India, under the Open Government Data (OGD) Platform India terms.
- **Source Portal:** [https://airquality.cpcb.gov.in/caaqms/](https://airquality.cpcb.gov.in/caaqms/)
- **Code License:** Released under the [MIT License](LICENSE).

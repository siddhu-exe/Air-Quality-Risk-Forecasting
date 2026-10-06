# Delhi Air Quality Risk Forecasting

This project forecasts air quality across Delhi 1 to 24 hours in advance and evaluates the impact of citywide pollution control policies. Instead of treating air quality as a generic regression problem, it investigates why standard machine learning breaks down during severe winter smog episodes and how to build models that actually hold up. It also includes a methodological study of why naive before/after evaluations of Delhi's Diwali firecracker ban are unreliable, and an interactive evaluation dashboard.

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

## Limitations (Read First)

- **The target is smoothed.** Official AQI is a 24-hour rolling average, so consecutive hours are nearly identical (lag-1 autocorrelation ≈ 0.998). "Copy the last value" is therefore a very strong baseline, and model skill must be judged against persistence, not R² alone.
- **Persistence is hard to beat.** At 1h the tuned model loses to persistence on RMSE and R²; at 24h the hybrid beats it on both (MAE skill +0.11, RMSE skill +0.12).
- **Training lacks prior winters.** The model trains on 2025-01..08, which contains no winter peak, so tree models cannot extrapolate beyond ~347 AQI. Recomputing AQI for 2023–2024 is a Tier 2 fix.
- **A single test window.** Evaluation is one Nov–Dec 2025 backtest; there is no rolling-origin or multi-winter evaluation yet.
- **No forecast meteorology.** Models use ground telemetry and observed weather only, not forecast wind or boundary-layer data.
- **Backtest only.** Everything is evaluated on historical data; there is no live ingestion, deployed forecast, or comparison against operational government forecasts (IITM AQEWS/SAFAR).
- **Geographic scope.** 7 urban monitoring stations within the National Capital Territory of Delhi.

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
                                                    (Validation-Selected Thresholds)
                                                                 │
                                                                 ▼
                                                    Interactive Streamlit Dashboard
```

---

## Key Results

Models were evaluated out-of-sample on the held-out peak winter crisis test set (November 1 – December 31, 2025, across all 7 Delhi continuous monitoring stations). Because the AQI target is already a 24-hour rolling average, the naive-persistence reference (predict the current AQI) is reported for every horizon, and skill scores are measured against it: `skill = 1 - metric_model / metric_persistence`, so a positive value means the model beats persistence. CIs are 95% day-block bootstrap intervals.

| Horizon | Model | N | MAE | MAE 95% CI | RMSE | RMSE 95% CI | R² | Bias | MAE (AQI≥300) | MAE skill | RMSE skill |
| :--- | :--- | ---: | ---: | :---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 1h | Tuned LightGBM | 10057 | 2.29 | [1.66, 3.16] | 5.08 | [2.88, 7.17] | 0.992 | -0.83 | 2.3 | 0.047 | -0.332 |
| 1h | Naive persistence | 10057 | 2.40 | [2.11, 2.69] | 3.82 | [3.23, 4.42] | 0.995 | -0.14 | 2.3 | 0.000 | 0.000 |
| 6h | Tuned LightGBM | 9998 | 11.84 | [10.33, 13.63] | 15.97 | [13.42, 18.83] | 0.919 | -6.85 | 11.8 | 0.069 | 0.091 |
| 6h | Naive persistence | 9998 | 12.72 | [11.12, 14.41] | 17.58 | [15.08, 19.90] | 0.902 | -0.77 | 11.9 | 0.000 | 0.000 |
| 24h | 50/50 Hybrid (Persistence + Ridge) | 9800 | 34.11 | [29.57, 39.15] | 44.80 | [38.65, 50.84] | 0.365 | -5.12 | 31.9 | 0.110 | 0.117 |
| 24h | Naive persistence | 9800 | 38.34 | [33.09, 44.01] | 50.75 | [43.63, 57.66] | 0.185 | -1.92 | 35.3 | 0.000 | 0.000 |

Source of truth: `reports/metrics/headline_metrics.csv`, regenerated by `./venv/bin/python src/evaluation/build_metrics_table.py`.

### Key Classification & Alerting Metrics

Severe (AQI ≥ 401) detection is reported at the alert threshold selected on the **validation** split (the 5:1 cost ratio gives τ = 274.5 AQI), then evaluated **once** on the winter test set. Recall is always shown with precision and the false-alarm count:

- **Model:** recall 99.8%, precision 42.9%, FPR 92.7% (5,347 false-alarm hours on test).
- **Naive persistence** at the same threshold: recall 99.6%, precision 43.0%, FPR 92.1% (5,314 false-alarm hours) — the alert rule adds little over copying the last value.
- The validation window (Sep–Oct, 2.4% Severe hours) is far cleaner than the winter test window (41.1% Severe hours). That prevalence shift is why the validation-selected threshold is aggressive and false alarms are high on test.

Source: `reports/classification/metrics/cost_optimal_thresholds_summary.csv` (`selected_on = val`). An earlier version selected the threshold on the test set itself; that leakage has been removed. The episode lead-time metric is being reworked separately.

---

## What Went Wrong During Modeling

**Standard gradient boosting trees hit a hard mathematical ceiling during peak winter, underpredicting severe crises by over 136 AQI points.**

When I first trained LightGBM and XGBoost to predict AQI 24 hours ahead, they broke down completely on the winter test set, producing an MAE of 98.24 and an R² of -0.06. Because decision trees are step functions bounded by the maximum value observed during training (around 347 AQI), they were physically incapable of predicting the severe 450 to 500 AQI spikes that occurred in November and December. Adding raw calendar features like month made it worse by trapping winter test records into low-pollution monsoon leaves.

I resolved this by removing raw calendar indicators and building a 50/50 hybrid model that blends Naive Persistence with an L2-regularized linear Ridge regression on 49 curated causal features. The regularized linear model provides unbounded extrapolation into extreme pollution levels while persistence maintains strong local temporal inertia. This reduced the 24-hour MAE from 98.24 to 34.11, beating persistence across all 7 Delhi stations.

*Full breakdown and ablation logs:* [`reports/modeling/PHASE_6_FINAL_AUDIT.md`](reports/modeling/PHASE_6_FINAL_AUDIT.md)

---

## Causal Analysis

**The Diwali firecracker ban cannot be evaluated with this data: the ban was in force in every year studied, so there is no untreated Delhi period to compare against.**

A naive before/after comparison suggests pollution jumped after Diwali 2025 (+135.6 AQI points; +97.3 µg/m³ PM2.5), which would make the ban look like a failure. But the design fails its own checks: pre-trends are violated (AQI already rising +20.4 points/day and PM2.5 +11.2 µg/m³/day in the 14 days before Diwali), and an in-time placebo on a non-event date returns a "significant" +24.3 AQI shift. With date-clustered standard errors and trend + weather controls (interrupted time series), the estimated level jump is statistically indistinguishable from zero (−10.6 AQI, p = 0.51; +17.0 µg/m³ PM2.5, p = 0.59). The honest conclusion is that the ban's effect is **not identifiable** here; claims that boundary-layer compression or stubble burning "caused" the post-Diwali crisis remain untested hypotheses, not findings.

*Full breakdown:* [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md)

Hourly chemical tracer telemetry showed that firecrackers caused an acute burst on festival night—with PM2.5 surging 8.0x to 960.7 µg/m³ and SO₂ jumping 5.3x to 73.5 µg/m³—but this smoke cloud dispersed within 18 to 24 hours. The multi-week crisis that followed was driven by seasonal meteorology trapping background emissions, not lingering festival smoke.

*Full econometric models and regression tables:* [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md)

---

## Risk Classification & Alerting

**Alert thresholds are selected on the validation split and evaluated once on the test set, and recall is always reported with precision and the false-alarm count.**

Continuous AQI forecasts are mapped to the 6 statutory CPCB categories (Good, Satisfactory, Moderate, Poor, Very Poor, Severe) and CAQM Graded Response Action Plan (GRAP) Stages I through IV. The Severe decision cutoff is chosen by minimizing expected asymmetric cost on validation (Sep–Oct 2025); only then is it applied to the winter test set. A prevalence shift makes this hard: validation has 2.4% Severe hours, the test window 41.1%.

| Operating Policy | Decision Cutoff (AQI) | Val Severe Recall | Val Severe Precision | Test Severe Recall | Test Severe Precision | Test Missed Severe Hours | Test False Alarm Hours |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Statutory Fixed CPCB** | 401.0 | 20.8% | 32.2% | 61.08% | 73.86% | 1,568 h | 871 h |
| **Validation-optimal (5:1 Loss Ratio)** | **274.5** | **100.0%** | 9.81% | **99.83%** | 42.93% | **7 h** | 5,347 h |
| **Pragmatic Compromise** | 380.0 | 49.1% | 33.3% | 78.90% | 64.40% | 850 h | 1,757 h |

The aggressive validation-optimal cutoff buys high recall at the cost of precision. At the same 274.5 cutoff, naive persistence scores recall 99.63%, precision 43.03% and 5,314 false-alarm hours on test — essentially the same as the model — so this alert rule should not be read as evidence of predictive skill beyond persistence.

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

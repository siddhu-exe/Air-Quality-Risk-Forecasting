# Delhi Air Quality Risk Forecasting & Causal Policy Evaluation

This system forecasts air quality across Delhi 1 to 24 hours in advance and evaluates the real-world impact of citywide pollution policies. Rather than assuming clean data and simple models, it focuses on where standard machine learning fails during severe winter smog crises and how to fix those failures.

## Project Links

- **Interactive Evaluation Dashboard:** [[DASHBOARD_URL]]
- **Cleaned Dataset on Kaggle:** [[KAGGLE_URL]]
- **GitHub Repository:** [https://github.com/Siddharth23052005/Air-quality-risk-forecasting](https://github.com/Siddharth23052005/Air-quality-risk-forecasting)

---

## What Broke and How I Fixed It

### 1. The 24-Hour Tree Extrapolation Ceiling (MAE 98.24 → 34.11)

**Standard tree models physically cannot predict pollution spikes higher than the worst day in their training set.**

When I first trained LightGBM and XGBoost to predict AQI 24 hours ahead, the models broke down completely during peak winter, averaging an error of 98.24 MAE. Because the training data peaked at 347 AQI, the trees hit a hard mathematical ceiling and underpredicted severe 400–500 AQI winter crises by over 136 points on average. Calendar features like month also trapped the trees into routing winter test records into low-pollution monsoon leaves. I fixed this by removing non-stationary calendar features and switching to a regularized Ridge regression blended 50/50 with persistence. This brought the 24-hour error down from 98.24 to 34.11 MAE, beating persistence across all 7 Delhi stations.

*Full breakdown and ablation logs:* [`reports/modeling/PHASE_5_BASELINE_REPORT.md`](reports/modeling/PHASE_5_BASELINE_REPORT.md)

### 2. The Diwali Firecracker Ban Pre-Trends Trap (Naive +135.57 → ITS -10.59)

**The raw +135 point post-Diwali surge was an illusion caused by the onset of winter, not a policy failure.**

A naive before-and-after comparison suggested AQI increased by 135.57 points after Diwali 2025, making the firecracker ban look like a failure. But checking pre-trends showed pollution was already rising by 20.38 points per day before the festival as winter weather set in and trapped emissions. Once I controlled for this pre-existing seasonal slope, temperature, wind speed, and station fixed effects with an Interrupted Time Series model, the policy effect collapsed to -10.59 AQI points (p = 0.425), statistically indistinguishable from zero. A placebo test run 30 days prior produced a fake 24.26 point "effect," confirming that raw comparisons pick up seasonal weather rather than policy impact.

*Full econometric models and regression tables:* [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md)

---

## Multi-Horizon Forecasting Results

Models were evaluated out-of-sample on the peak winter crisis test split (November 1 – December 31, 2025; N = 9,800 hourly observations across 7 continuous monitoring stations).

| Horizon | Model Architecture | Test MAE | Test RMSE | Test R² | Naive Baseline MAE | Why This Architecture |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1-Hour** | Tuned LightGBM | **2.29** | 3.65 | 0.9958 | 2.40 | AQI is reported as a 24h rolling average, giving it high 1-hour inertia. LightGBM edges out persistence by picking up short-term particulate acceleration. |
| **6-Hour** | Tuned LightGBM | **11.84** | 16.71 | 0.9126 | 14.73 | Captures intra-day diurnal patterns (traffic peaks and boundary layer compression) that simple persistence lags behind on. |
| **24-Hour** | 50/50 Hybrid Persistence + Ridge (alpha=1000) | **34.11** | 44.80 | 0.3647 | 38.34 | Linear model provides regularized, unbounded extrapolation during extreme winter spikes without the clipping failures of tree models. |

An R² of 0.36 at 24 hours represents real, modest predictive skill over baseline heuristics. Predicting atmospheric dispersion a full day ahead in a landlocked basin carries fundamental physical limits when relying on ground telemetry without numerical weather simulation models.

---

## Causal Policy Finding

**Firecrackers cause an acute 18–24 hour pollution spike on festival night, but they do not drive Delhi's multi-week winter smog crisis.**

Hourly chemical tracer telemetry shows that firecrackers produced a sharp, short-lived burst on Diwali night, with PM2.5 surging 8.0x to 960.7 µg/m³ and SO₂ jumping 5.3x to 73.5 µg/m³ despite the legal ban. However, this combustion cloud dispersed completely within 18 to 24 hours. The prolonged multi-week winter pollution emergency in Delhi is driven by regional meteorology—thermal inversion, falling boundary layer heights, and calm winds trapping background emissions—rather than lingering festival smoke.

*Full econometric models, regression tables, and coefficient forest plots:* [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md)

---

## Cost-Aware Risk Thresholds

**Lowering the 24-hour Severe alert trigger from 401 to 341.5 AQI catches 95.7% of hazardous pollution crises.**

The statutory CPCB cutoff (AQI ≥ 401) misses 38.92% of Severe hours at a 24-hour horizon because regularized models naturally pull extreme predictions toward the mean. Using an asymmetric 5:1 public health loss ratio—where missing a hazardous day is penalized 5x more than a false alarm—the optimal operating threshold drops to 341.5 AQI. This catches 95.71% of severe crisis hours (an 89% reduction in missed hazardous exposure). While false alarms increase to roughly one per true alarm, 93.6% of those false alarms occur when the air is already "Very Poor" (301–400 AQI), and exactly 0% occur in clean or moderate air.

| Operating Policy | Cutoff (AQI) | Severe Recall | Severe Precision | Missed Severe Hours | False Alarm Hours |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Statutory Fixed CPCB** | 401.0 | 61.08% | 73.86% | 1,568 h | 871 h |
| **Cost-Optimal (5:1 Ratio)** | **341.5** | **95.71%** | 54.33% | **173 h** | 3,242 h |
| **Pragmatic Compromise** | 380.0 | 78.90% | 64.40% | 850 h | 1,757 h |

*Full optimization curve, loss matrices, and 1:1 to 20:1 sensitivity sweeps:* [`reports/classification/cost_aware_threshold_analysis.md`](reports/classification/cost_aware_threshold_analysis.md)

---

## Database Architecture & Schema

The data layer runs on PostgreSQL 16 using a 4-table relational schema designed for full lineage traceability and idempotent ingestion.

![Database ERD Schema](docs/Database/Blank%20diagram.png)

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

### Why It Is Structured This Way
- **Source Lineage (`source_files`):** Every hourly measurement references its raw source file and ingestion batch for end-to-end auditability.
- **Idempotent Ingestion:** A `UNIQUE(station_id, timestamp)` constraint enables `ON CONFLICT DO UPDATE` loads that prevent duplicates and allow retroactively corrected values to update in place.
- **Non-Destructive QC (`qc_flags`):** Corrupted sensor sentinels (e.g. `-999`) nullify only the damaged metric while logging a JSON flag, preserving the rest of the hourly record.

---

## Repository Structure

```text
.
├── app.py                      # Root entrypoint for Streamlit Community Cloud
├── dashboard/                  # Multi-tab interactive Streamlit evaluation dashboard
├── data/
│   ├── processed/              # Clean 124-feature Parquet matrix (features_2025.parquet)
│   └── ml/                     # Versioned ML training datasets (1h, 6h, 24h Parquets)
├── docs/                       # Technical reference notes, timelines, and findings
├── etl/                        # Pipeline scripts (discovery, transformation, PostgreSQL loading)
├── models/                     # Serialized production model artifacts (LightGBM, Ridge)
├── notebooks/                  # Google Colab training, optimization, and refinement notebooks
├── profiling/                  # Schema scanners and raw data discovery utilities
├── reports/                    # Comprehensive research reports, figures, and CSV metrics
│   ├── causal/                 # Diwali econometric analysis, regression summaries, and figures
│   ├── classification/         # CPCB/GRAP metrics, episode lead times, cost-aware analyses
│   ├── eda/                    # Exploratory data analysis charts and statistical profiling
│   ├── modeling/               # Multi-horizon baseline benchmarks and ablation logs
│   ├── phase5_features/        # Causal feature definitions and zero-leakage audits
│   └── phase7_classification/  # Regulatory CPCB and GRAP alerting specifications
├── sql/                        # Canonical PostgreSQL migrations (001_schema through 006)
├── src/                        # Source codebase for feature engineering, modeling, and causal stats
├── tests/                      # Automated timestamp boundary checks and DB validation scripts
├── requirements.txt            # Minimal runtime dependencies
└── README.md                   # Canonical project documentation
```

---

## Data Sources & License Note

- **Data Origin:** Continuous Ambient Air Quality Monitoring Stations (CAAQMS) telemetry and Air Quality Index (AQI) reports published by the Central Pollution Control Board (CPCB) and DPCC, Government of India.
- **Data Coverage:** 7 continuous stations in Delhi (Anand Vihar, Bawana, Dwarka-Sector 8, ITO, Jahangirpuri, Punjabi Bagh, R K Puram) spanning 2023–2026.
- **Redistribution:** Raw government spreadsheets are not tracked in this repository; cleaned and structured datasets are published on Kaggle: [[KAGGLE_URL]].

---

## Known Limitations

1. **24-Hour Forecast Skill:** While the hybrid model beats persistence (R² = 0.36 vs 0.18), multi-day forecasting in Delhi is constrained by sudden atmospheric stagnation that requires numerical weather simulation models to fully resolve.
2. **Single Causal Policy Window:** The causal analysis evaluates the Diwali firecracker ban across three festival instances (2023–2025), rather than all clean air policies in Delhi.
3. **No External City Control:** Historical 2023–2025 data for Mumbai was unpopulated in the raw records, requiring within-city Interrupted Time Series controls instead of a Difference-in-Differences setup.
4. **Historical Backtest System:** The dashboard and models currently operate as a backtest against held-out historical data (Nov–Dec 2025) rather than a live streaming pipeline.

---

## Production Considerations
<!-- TODO: add when requested -->

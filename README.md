# Delhi Air Quality Risk Forecasting & Causal Policy Evaluation

Most air quality projects download a clean CSV, train a Random Forest on random train/test splits, and report an $R^2$ of 0.95 without realizing the model is simply memorizing near-instant persistence or leaking future timestamps. 

This project is an end-to-end data engineering, forecasting, and econometric analysis system built from raw Central Pollution Control Board (CPCB) monitoring data in Delhi (2023–2026). It covers the full lifecycle: building an idempotent PostgreSQL pipeline to handle corrupted timestamps and sensor sentinels, developing leakage-audited multi-horizon forecasting models ($1\text{h}, 6\text{h}, 24\text{h}$), diagnosing why standard decision trees fail during extreme winter pollution spikes, evaluating the Delhi Diwali firecracker ban using quasi-experimental causal inference, and reframing public health alerts under asymmetric loss functions.

## Project Links

- **Interactive Evaluation Dashboard:** [[DASHBOARD_URL]]
- **Cleaned Dataset on Kaggle:** [[KAGGLE_URL]]
- **GitHub Repository:** [https://github.com/Siddharth23052005/Air-quality-risk-forecasting](https://github.com/Siddharth23052005/Air-quality-risk-forecasting)

---

## What Broke and How I Fixed It

Real data science is mostly debugging where assumptions fail in the real world. Two major components of this project failed on the first attempt; here is what went wrong and how I fixed them.

### 1. The 24-Hour Tree Extrapolation Ceiling (MAE 98.24 &rarr; 34.11)

When I first trained Gradient Boosted Decision Trees (LightGBM and XGBoost) to predict AQI 24 hours ahead, the models performed well on the validation set but broke down on the peak winter test set (November–December 2025), producing an error of $\text{MAE} = 98.24$. 

When I investigated the sample-level errors, I discovered two distinct failure modes:
1. **The Extrapolation Ceiling:** Decision trees partition feature space into rectangular boxes and output the mean of training targets inside each leaf. In the Jan–Aug training data, the maximum recorded AQI was $347.61$. When the winter test set experienced extreme pollution spikes where actual AQI reached $400\text{--}500$ (averaging $429.49$), the tree literally could not output a number higher than $347.61$. The model hit an artificial ceiling, underpredicting winter crises by over 136 points on average.
2. **Non-Stationary Calendar Traps:** Ordinal temporal features like `month` and `day_of_year` caused the trees to learn spurious splits. Because months 11 and 12 were not in the training set, the trees split on `month > 6.5` (monsoon season) and routed severe winter test records into low-pollution monsoon leaves ($\text{AQI} \approx 85$).

```text
TRAINING DATA (Jan–Aug):  Max AQI = 347.61  ───► Tree splits create hard ceiling at 347.61
WINTER TEST SET (Nov–Dec): True AQI = 450.00 ───► Tree outputs 347.61 (Underprediction: -102.39)
```

**The Fix:** I removed non-stationary calendar variables, pruned the feature set down to 49 causal pollutant and lag features, and switched to a regularized linear model (Ridge regression with $\alpha=1000$) blended 50/50 with naive persistence. Unlike decision trees, Ridge regression fits an unbounded continuous hyperplane, allowing predictions to scale naturally into severe territory without artificial caps. This brought the 24-hour test error down from $98.24$ to **$34.11$ MAE**, outperforming persistence across all 7 Delhi stations.

### 2. The Diwali Firecracker Ban Pre-Trends Trap (Naive +135.57 &rarr; ITS -10.59)

I wanted to measure whether Delhi's blanket ban on firecrackers during Diwali reduced pollution. A naive before-and-after comparison of the 14 days before vs. 14 days after Diwali 2025 showed that average AQI increased by **$+135.57$ points** ($p < 0.001$). Taken at face value, this would suggest the policy completely failed and worsened air quality.

Before trusting that number, I tested the parallel pre-trends assumption required for valid causal inference. It failed completely: daily AQI was already escalating at **$+20.38$ points per day** ($p < 0.001, R^2 = 0.77$) during the two weeks *before* Diwali. Delhi's air quality naturally deteriorates every October and November as seasonal temperatures drop, planetary boundary layer heights fall below 300 meters, and calm winds trap background emissions. The naive comparison was confusing the seasonal onset of winter with the impact of the festival.

```text
NAIVE COMPARISON:       Post-Diwali vs Pre-Diwali Mean ──► +135.57 AQI (Confounded by winter onset)
PRE-TREND AUDIT:        Pre-Diwali Trajectory          ──► +20.38 AQI / day (Pre-trends violated)
INTERRUPTED TIME SERIES: Controlling for Trend & Weather ──► -10.59 AQI (p = 0.425, Statistically Zero)
```

**The Fix:** Because Mumbai data in the repository did not cover the 2023–2025 period to serve as an external control city, I used an Interrupted Time Series (ITS) regression that explicitly controls for the pre-existing upward slope, weather factors (temperature, relative humidity, wind speed), and station fixed effects. Controlling for the seasonal trend reduced the estimated immediate policy shift to **$-10.59$ AQI points** ($p = 0.425, 95\%\text{ CI: } [-36.61, +15.43]$), which is statistically indistinguishable from zero. An in-time placebo test run on a random non-event date 30 days prior produced a fake "effect" of $+24.26$ points ($p < 0.001$), confirming that unadjusted comparisons pick up seasonal weather traps rather than policy effects.

---

## Multi-Horizon Forecasting Results

Models were evaluated out-of-sample on the peak winter crisis test split (November 1 – December 31, 2025; $N = 9,800$ hourly observations across 7 continuous monitoring stations).

| Horizon | Model Architecture | Test MAE | Test RMSE | Test $R^2$ | Naive Baseline MAE | Why This Architecture |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1-Hour** | Tuned LightGBM | **2.29** | 3.65 | 0.9958 | 2.40 | AQI is reported as a 24h rolling average, giving it high 1-hour inertia. LightGBM edges out persistence by picking up short-term particulate acceleration. |
| **6-Hour** | Tuned LightGBM | **11.84** | 16.71 | 0.9126 | 14.73 | Captures intra-day diurnal patterns (traffic peaks and boundary layer compression) that simple persistence lags behind on. |
| **24-Hour** | 50/50 Hybrid Persistence + Ridge ($\alpha=1000$) | **34.11** | 44.80 | 0.3647 | 38.34 | Linear model provides regularized, unbounded extrapolation during extreme winter spikes without the clipping failures of tree models. |

*Note on 24-hour performance:* An $R^2$ of 0.36 represents real, modest predictive skill over baseline heuristics, but it is not a solved problem. Predicting atmospheric dispersion a full day ahead in a landlocked basin subject to sudden meteorological stagnation carries fundamental chaotic limits when relying on ground telemetry alone without numerical weather simulation models.

---

## Causal Policy Finding

A granular look at hourly chemical tracers shows what the Diwali ban actually did:
- **Acute Spike (Short-Term Non-Compliance):** On Diwali night, hourly $\text{PM}_{2.5}$ peaked at $960.7\ \mu\text{g/m}^3$ (an 8.0x surge over baseline) and sulphur dioxide ($\text{SO}_2$) chemical tracers spiked 5.3x to $73.5\ \mu\text{g/m}^3$, confirming widespread short-term firecracker bursting despite the legal ban.
- **Rapid Dispersion:** This combustion burst dissipated within 18–24 hours as particulate matter deposited and dispersed.
- **The Core Finding:** Firecrackers create a short, acute spike that lasts less than a day. The prolonged, multi-week winter smog crisis in Delhi is driven by meteorological thermal inversion, low wind speeds, and regional background emissions—not weeks of lingering firecracker smoke.

Full econometric models, regression tables, and coefficient forest plots are documented in [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md).

---

## Cost-Aware Risk Thresholds

Standard policy frameworks like CPCB and GRAP use fixed numerical cutoffs (e.g. $\text{AQI} \ge 401$ triggers Severe / GRAP Stage III emergency interventions). When applied directly to 24-hour predictions, this statutory threshold misses **38.92% of Severe hours** (Recall = 61.08%) because regularized regression shrinks extreme predictions toward the mean.

Using cost-sensitive decision theory, I evaluated the threshold under an asymmetric **5:1 public health loss ratio** ($C_{\text{FN}} = 5 \cdot C_{\text{FP}}$), where missing a hazardous day (unmitigated public exposure) is penalized 5x more heavily than a false alarm (unnecessary construction pause):

| Operating Policy | Cutoff ($\tau$) | Severe Recall | Severe Precision | Missed Severe Hours | False Alarm Hours |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Statutory Fixed CPCB** | $401.0$ AQI | 61.08% | 73.86% | 1,568 h | 871 h |
| **Cost-Optimal (5:1 Ratio)** | **$341.5$ AQI** | **95.71%** | 54.33% | **173 h** | 3,242 h |
| **Pragmatic Compromise** | $380.0$ AQI | 78.90% | 64.40% | 850 h | 1,757 h |

Lowering the operational trigger to $\tau^* = 341.5$ catches **95.71% of severe crisis hours** (an 89.0% reduction in missed hazardous exposure). The cost is roughly 1 false alarm for every true alarm, but **93.6% of those false alarms happen when the air is already "Very Poor" ($301\text{--}400$ AQI)**, and exactly **0.0%** occur in clean or moderate air.

The full optimization curve, mathematical loss matrix, and sensitivity sweeps across 1:1 to 20:1 ratios are in [`reports/classification/cost_aware_threshold_analysis.md`](reports/classification/cost_aware_threshold_analysis.md).

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
- **Source Lineage (`source_files`):** Government CAAQMS data arrives in scattered, irregular monthly CSVs and XLSX files. By isolating source metadata into its own table, every single hourly reading in the database points directly to the raw file and processing run that created it.
- **Idempotent Ingestion:** Both `caaqms_hourly` and `aqi_hourly` enforce a `UNIQUE(station_id, timestamp)` constraint. Re-running the pipeline over previously loaded months executes `ON CONFLICT (station_id, timestamp) DO UPDATE`, preventing duplicate rows while allowing retroactively corrected sensor values to update in place.
- **Non-Destructive QC (`qc_flags`):** Sensor errors or sentinels (e.g. `-999`, clipped barometric pressures) nullify only the corrupted measurement field, preserving the rest of the hourly record while recording a JSON flag (e.g. `{"pm25": "SENTINEL_-999"}`) in `qc_flags`.

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

- **Data Origin:** Continuous Ambient Air Quality Monitoring Stations (CAAQMS) telemetry and Air Quality Index (AQI) reports published by the Central Pollution Control Board (CPCB) and Delhi Pollution Control Committee (DPCC), Government of India.
- **Data Coverage:** 7 continuous stations in Delhi (Anand Vihar, Bawana, Dwarka-Sector 8, ITO, Jahangirpuri, Punjabi Bagh, R K Puram) spanning 2023–2026.
- **Redistribution:** Raw government source spreadsheets are not tracked in this repository due to size and licensing considerations. The cleaned, structured, and feature-engineered datasets are published on Kaggle: [[KAGGLE_URL]].

---

## Known Limitations

1. **24-Hour Forecast Skill:** While the 24-hour hybrid model beats persistence baselines ($R^2 = 0.36$ vs $0.18$), variance explained is modest. Accurate multi-day air quality forecasting in Delhi requires coupled chemical transport models (like WRF-Chem) that simulate regional boundary layer meteorology.
2. **Single Causal Policy Window:** The causal analysis evaluates the Diwali firecracker ban across three festival instances (2023–2025). It is a targeted evaluation of firecracker policy, not a comprehensive assessment of all clean air interventions in Delhi.
3. **No External City Control:** Because historical 2023–2025 data for Mumbai was unpopulated in the raw records, an external Difference-in-Differences design against Mumbai was precluded, requiring within-city Interrupted Time Series controls instead.
4. **Historical Backtest System:** The current dashboard and models operate as a backtest against held-out historical data (Nov–Dec 2025). Live deployment requires connecting a real-time data ingestion scraper to CPCB's daily publishing endpoints.

---

## Production Considerations
<!-- TODO: add when requested -->

# Simple Timeline: Project Progress

*A plain-English timeline showing exactly where we are in building the Air Quality system.*

## Step 1: Getting the Data (Done)
- **What we did:** Gathered all the historical air quality and weather files for Delhi and Mumbai.
- **What we found:** The data comes in different shapes. Delhi has extremely detailed hourly spread sheets for individual stations, while Mumbai has general city-level data. The files were slightly messy and needed a lot of cleaning.

## Step 2: Cleaning and Organizing (Done)
- **What we did:** Built the software that reads every single file, checks it for errors, cleans it up, and gets it ready for a database. 
- **Big Wins:**
  - **Fixed the Dates:** We found out the system was reading dates incorrectly (thinking December 2025 was actually the year 1970). We fixed this by teaching the software to read the Year and Month from the file's name instead.
  - **Stopped Deleting Good Data:** Initially, the system threw away perfectly good temperatures and pollution readings (like 9°) because it thought "9" was an error code. We fixed it to only delete obvious machine glitches (like "-999").
  - **Preserving Records:** Instead of throwing out a whole hour of data because one sensor broke, our system now marks just that one cell as "empty" but keeps the rest of the information intact. 
- **Result:** We successfully recovered and cleaned over 220,000 hourly rows of data accurately.

## Step 3: Setting up the Database & Loading Data (Done)
- **What we did:** Created a fast, permanent local database (PostgreSQL on port 5433) with zero heavy Docker overhead. Built an automatic batch-loader that inserts and updates records cleanly with perfect idempotency.
- **Result:** Loaded 105 raw files without a single error — populating **162,096 hourly pollutant records** and **57,946 AQI observations** across all 7 Delhi stations.

## Step 4: Exploring Patterns & Statistics (EDA) (Done)
- **What we did:** Ran deep statistical queries directly inside the database to uncover seasonal, hourly, spatial, and weather patterns. Created 11 clear, publication-quality charts.
- **Key Findings:**
  - **Citywide Airshed Sync:** All 7 Delhi stations move together closely ($r \ge 0.92$), proving air pollution is a regional, city-wide event.
  - **Daily Rhythm:** Pollution spikes sharply at 07:00 (morning traffic) and 23:00 (night inversion/boundary layer collapse), while Ozone peaks at 14:00 with sunlight.
  - **Winter Crisis:** 123 severe pollution episodes (>400 AQI) occurred, clustered heavily in November through January.
  - **Memory/Persistence:** Today's AQI is strongly correlated with yesterday's AQI ($r \approx 0.998$), giving us strong baselines for forecasting.

## Step 5: Feature Engineering & Baseline Benchmarking (Done)
- **What we did:** Created 124 mathematical features across 7 distinct groups (past hourly pollution readings, rolling averages, weather conditions, season flags, and citywide neighborhood signals). Tested simple benchmark forecasts (e.g. predicting current AQI continues unchanged).
- **Key Findings:**
  - **1-Hour Forecasts:** Predicting that current AQI stays unchanged is extremely accurate ($\text{MAE} \approx 2.4$), because official AQI is already a 24-hour moving average.
  - **6-Hour Forecasts:** Persistence is moderately reliable ($\text{MAE} \approx 12.7$), but starts missing afternoon ozone spikes and night boundary layer collapses.
  - **24-Hour Forecasts:** Persistence completely breaks down during the winter crisis ($\text{MAE} \approx 38.3, R^2 \approx 0.18$), proving that complex machine learning models with weather and spatial awareness are required for next-day forecasts.
  - **Leakage-Safe Data:** Verified mathematically that future data never leaks backward into the past.

## Step 6: Multi-Horizon Forecasting & 24h Model Optimization (Done)
- **What we did:** Trained and validated machine learning models across 1-hour, 6-hour, and 24-hour forecasting windows. Conducted deep root-cause failure investigations when models struggled with next-day winter forecasts:
  - **1-Hour Forecast (Validated):** Tuned LightGBM model achieves an error of just **2.29 AQI points**, beating persistence (2.40).
  - **6-Hour Forecast (Validated):** Tuned LightGBM achieves an error of **11.84 AQI points**, substantially outperforming persistence (14.73) and anticipating intra-day pollution shifts.
  - **24-Hour Failure Root Cause & Breakthrough (Phase 6B):** 
    - *Why Standard Trees Failed:* Decision trees cannot extrapolate beyond numbers they saw in training (capping predictions at 347 even when winter AQI soared above 450), and split on calendar months, mistaking winter crisis days for clean monsoon days.
    - *The Fix:* We pruned non-stationary calendar traps and built a Regularized Linear Ridge model on core AQI and pollutant lags combined with a Hybrid Persistence Ensemble.
    - *The Result:* Achieved an error of **35.48 AQI points** ($R^2 = 0.3123$), soundly beating Naive Persistence (38.34 AQI points) across **all 7 Delhi stations**.
- **Result:** Complete multi-horizon forecasting suite verified, saved in `models/{1h,6h,24h}/`, and reproducible via Colab notebooks `notebooks/phase_6_colab_training.ipynb` and `notebooks/phase_6b_24h_optimization.ipynb`.

## Step 6C: Final 24-Hour Forecast Refinement (Done)
- **What we did:** Finalized and elevated the 24-hour forecasting model by adding multi-day causal tracking features (up to 7-day rolling statistics and spatial network signals) and optimizing blend weights strictly on the validation set.
- **Key Results:**
  - **Best-in-Class Winter Performance:** Achieved an error of **34.11 AQI points** ($R^2 = 0.3647, \text{MAPE} = 9.72\%$), outperforming Naive Persistence (38.34) by **+4.23 AQI points** and beating Phase 6B by **+1.37 AQI points**.
  - **100% Station Superiority:** Outperformed persistence across all 7 Delhi stations (+2.47 to +5.22 AQI points).
  - **Production Artifacts:** Saved all final models, feature scalers, imputers, schemas, and metadata to `models/24h/final/`, and interactive training notebook to `notebooks/phase_6c_24h_final_refinement.ipynb`.

## Step 7: Risk Classification & Real-World Alerts (Done)
- **What we did:** Converted numerical AQI forecasts into official government health risk categories (CPCB 6-tier system: Good, Satisfactory, Moderate, Poor, Very Poor, Severe) and emergency action stages (CAQM GRAP Stages I–IV). Evaluated how reliably forecasts give advance notice before severe pollution crises hit.
- **Key Results:**
  - **Zero Critical Misses:** At every single horizon (1h, 6h, and 24h), the system achieved a **0.000% critical miss rate** — it never dangerously predicts clean/moderate air when a severe emergency actually occurs.
  - **1-Hour Immediate Alerting:** Near-perfect precision (Macro F1 = **0.945**, Severe Recall = **98.4%**), acting as an instant, zero-lag verification.
  - **6-Hour Intra-Day Warning:** High operational reliability (Macro F1 = **0.657**, Severe Recall = **83.2%**), capturing morning-to-afternoon shifts.
  - **24-Hour Policy Window & Early Warning:** Successfully detects **93.2%** of hazardous stagnation events (Very Poor + Severe) and provides an average advance warning of **17.4 hours** (over 55% of crises flagged $\ge 6$ hours in advance), giving city authorities crucial time to enforce anti-pollution measures.
- **Result:** Classification framework fully audited and frozen in `reports/classification/PHASE_7_FINAL_AUDIT.md`.

## Step 8: Production Deployment, Real-Time Inference & Dashboard (Next)
- **Where we are heading:** 
  - Building a real-time automated inference pipeline that ingests new hourly station data, computes features, generates multi-horizon predictions, and assigns GRAP alerts.
  - Developing a lightweight REST API (FastAPI) and interactive dashboard (Streamlit) for live map visualizations, trend forecasting, and policy intervention tracking across Delhi.
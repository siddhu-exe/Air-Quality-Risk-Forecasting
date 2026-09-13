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

## Step 6: Dataset Versioning & Cloud Machine Learning Pipeline (In Progress)
- **What we did:** To prevent burning up the laptop's CPU, we split our workflow between local data prep and cloud machine learning:
  - **Local Preparation:** Packaged the 124 features into clean, versioned files for 1-hour, 6-hour, and 24-hour forecasting targets, complete with security checksums (SHA-256).
  - **Google Colab Training Suite:** Built an interactive, 16-step training notebook in Google Colab that trains modern Machine Learning models (LightGBM, XGBoost, and Ridge Regression), automatically searches for the best settings (Optuna), measures which feature groups matter most, and checks how well models predict severe winter pollution spikes (>300 AQI).
- **Result:** Versioned ML datasets ready in `data/processed/ml/` and Colab notebook ready in `notebooks/phase_6_colab_training.ipynb`.

## Step 7: Risk Classification & Real-World Alerts (Next)
- **Where we are heading:** Converting continuous forecasts into actionable health risk categories (e.g. CPCB AQI bands, GRAP emergency intervention stages) with false-alarm minimization.
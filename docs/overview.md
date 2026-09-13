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
FEATURE ENGINEERING        <-- (We are here - Phase 5)
        ↓
AQI FORECASTING
        ↓
RISK CLASSIFICATION
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

## Infrastructure & Compute
To ensure this repository remains ultra-lightweight and battery-friendly for local laptop development, we do **not** use Docker or heavy virtual machines. The entire database is a fully isolated, native PostgreSQL cluster running directly out of the `local_pg_data` folder on port `5433`. It uses virtually zero background resources and can be spun up or down instantly.

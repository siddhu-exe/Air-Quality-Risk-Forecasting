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
POSTGRESQL CURATED DATA    <-- (We are here)
        ↓
DATA VALIDATION
        ↓
EDA (Exploratory Data Analysis)
        ↓
FEATURE ENGINEERING
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
- **Primary Set (Delhi):** Station-level measurements containing distinct environmental pollutants (PM2.5, NOx, Ozone, etc.) and meteorological weather data at hourly resolution across 7 distinct sensors.
- **Secondary Set (Mumbai):** City-level AQI data reserved for future out-of-sample validation and external comparison. 

## Architectural Philosophy
Data integrity is paramount. If a sensor breaks and reports `PM10 = -999`, we do not throw away the entire row and lose the perfectly valid Temperature records for that hour. We gracefully NULL the broken cell and log the reason in a dedicated quality control database component. We trace every single row of data back to its original raw file source, meaning this entire architecture behaves identically to a secure, auditable, high-grade enterprise data warehouse.
## Infrastructure & Compute
To ensure this repository remains ultra-lightweight and battery-friendly for local laptop development, we do **not** use Docker or heavy virtual machines. The entire database is a fully isolated, native PostgreSQL cluster running directly out of the `local_pg_data` folder. It uses virtually zero background resources and can be spun up or down instantly.

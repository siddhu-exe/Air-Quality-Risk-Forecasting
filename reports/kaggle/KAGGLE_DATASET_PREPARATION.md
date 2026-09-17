# Kaggle Dataset Preparation & Validation Report

**Status:** COMPLETE & VERIFIED  
**Date:** 2026-09-17  
**Dataset Name:** Delhi Air Quality Monitoring Dataset (Hourly, 2023–2026)  
**Target Package Directory:** `kaggle/` (Git-ignored)

---

## 1. Executive Summary

This report documents the preparation, curation, and automated validation of the public tabular dataset package generated for Kaggle from the project's PostgreSQL 16 relational database (`air_quality_db`).

The export strictly adheres to public sharing standards:
- All internal filesystem paths (e.g., `/home/siddharth/...`), database connection parameters, and internal surrogate IDs were completely stripped.
- Raw government source files (`Og Data/`) were not copied or altered; curated data was exported directly from the validated PostgreSQL layer.
- Zero ML features or leakage-sensitive matrices were included.
- The `kaggle/` directory is isolated and registered in `.gitignore` to prevent committing tabular data or archives to GitHub.

---

## 2. Package Manifest & File Statistics

| File | Rows | Columns | File Size | Primary Key / Index | Description |
|---|:---:|:---:|:---:|---|---|
| `kaggle/caaqms_hourly.csv` | **162,096** | 24 | 19.93 MB | `(station_id, timestamp)` | Hourly multi-pollutant (12 parameters) & meteorology (8 parameters) with QC flags. |
| `kaggle/aqi_hourly.csv` | **57,946** | 5 | 2.14 MB | `(station_id, timestamp)` | Official CPCB-calculated hourly Air Quality Index (0–500 scale) for 2025. |
| `kaggle/stations.csv` | **7** | 6 | 0.44 KB | `station_id` | Metadata for 7 continuous monitoring stations across Delhi. |
| `kaggle/source_files.csv` | **105** | 9 | 15.68 KB | `source_file_id` | Sanitized provenance mapping observations back to source telemetry batches. |
| `kaggle/column_metadata.csv` | **44** | 5 | 4.89 KB | `(file, column)` | Column-level dictionary specifying descriptions, units, and data types for Kaggle UI. |
| `kaggle/README.md` | — | — | 9.30 KB | — | Comprehensive 10-section dataset documentation formatted for Kaggle. |

**Total Public Observation Rows:** 220,042  
**Total Package Size:** 22.09 MB

---

## 3. Coverage & Station Registry

- **Geographic Coverage:** National Capital Territory of Delhi, India
- **Temporal Resolution:** Hourly (discrete 1-hour reporting interval)
- **Timezone Anchor:** Asia/Kolkata (`UTC+05:30`)
- **Temporal Range:**
  - `caaqms_hourly.csv`: `2023-01-01 00:00:00+05:30` to `2026-08-31 23:00:00+05:30` (44 months)
  - `aqi_hourly.csv`: `2025-01-01 00:00:00+05:30` to `2025-12-31 23:00:00+05:30` (12 months)
- **Monitoring Stations (7 Total):**

| Station ID | Station Name | Operator | City | Status |
|:---:|---|:---:|:---:|:---:|
| 3 | Anand Vihar | DPCC | Delhi | Active |
| 4 | Bawana | DPCC | Delhi | Active |
| 5 | Dwarka-Sector 8 | DPCC | Delhi | Active |
| 6 | ITO | CPCB | Delhi | Active |
| 7 | Jahangirpuri | DPCC | Delhi | Active |
| 8 | Punjabi Bagh | DPCC | Delhi | Active |
| 9 | R K Puram | DPCC | Delhi | Active |

---

## 4. Column Schema & Data Types

### `caaqms_hourly.csv` (24 Columns)
- **Identifiers & Time:** `station_id` (int), `source_file_id` (int), `timestamp` (ISO 8601 string with `+05:30`)
- **Pollutants ($\mu\text{g/m}^3$ / ppb / $\text{mg/m}^3$):** `pm25`, `pm10`, `no`, `no2`, `nox`, `nh3`, `so2`, `co`, `o3`, `benzene`, `toluene`, `xylene`
- **Meteorology:** `temperature` (°C), `humidity` (%), `wind_speed` (m/s), `wind_direction` (0–360°), `rainfall` (mm), `solar_radiation` ($\text{W/m}^2$), `barometric_pressure` (mmHg), `vertical_wind_speed` (m/s)
- **Quality Control:** `qc_flags` (JSON string documenting non-destructive sentinel adjustments)

### `aqi_hourly.csv` (5 Columns)
- `station_id` (int), `source_file_id` (int), `timestamp` (ISO 8601 string), `aqi_value` (float, 0–500), `qc_flags` (JSON string)

### `source_files.csv` (9 Columns)
- `source_file_id` (int), `station_id` (int), `filename` (sanitized string), `source_type` (CAAQMS/AQI), `file_format` (CSV/XLSX), `reporting_period_start` (ISO string), `reporting_period_end` (ISO string), `row_count` (int), `processing_status` ("loaded")

---

## 5. Automated Validation & Integrity Verification

An automated verification suite (`tests/validate_kaggle_export.py`) was executed on the generated CSV files using pandas. All assertions passed without errors:

1. **Row Count Verification:** Exact match against PostgreSQL database tables:
   - `stations.csv`: 7 / 7 (100%)
   - `source_files.csv`: 105 / 105 (100%)
   - `caaqms_hourly.csv`: 162,096 / 162,096 (100%)
   - `aqi_hourly.csv`: 57,946 / 57,946 (100%)
   - `column_metadata.csv`: 44 / 44 (100%)
2. **Duplicate Check:** Evaluated `(station_id, timestamp)` uniqueness across all tables. **0 duplicate records detected.**
3. **Foreign Key Integrity:** 100% of `station_id` values reference valid station records in `stations.csv` ($ID \in \{3, 4, 5, 6, 7, 8, 9\}$). 100% of `source_file_id` values reference valid source batches in `source_files.csv`.
4. **Physical Range Bounds:**
   - $\text{PM}_{2.5} \in [1.00, 998.00]\ \mu\text{g/m}^3$
   - $\text{AQI} \in [31.0, 500.0]$ (strictly within CPCB scale)
   - Temperature, humidity, pressure, and wind vectors within valid physical limits.
5. **Encoding & Format:** UTF-8 encoding verified across all files; zero accidental index columns (no `Unnamed: 0`).
6. **Path Sanitization:** Confirmed zero occurrences of local host paths (`/home/...`, `local_pg_data/...`) in exported metadata.

---

## 6. Source, Provenance & License

- **Source Authority:** Central Pollution Control Board (CPCB) and Delhi Pollution Control Committee (DPCC), Ministry of Environment, Forest and Climate Change, Government of India.
- **Data Access Point:** Continuous Ambient Air Quality Monitoring Network ([https://airquality.cpcb.gov.in/caaqms/](https://airquality.cpcb.gov.in/caaqms/)).
- **License Status:** Open Government Data (OGD) Platform India terms. Users must provide appropriate attribution to CPCB and DPCC.

---

## 7. Git Security Verification

- **`.gitignore` Rule:** `kaggle/` is explicitly listed under untracked local exports.
- **Git Status Output:** Confirmed with `git status --ignored` that `kaggle/` is ignored by Git. No CSV or ZIP files are staged or committed.

---

## 8. Suggested Kaggle Presentation Metadata

- **Title:** `Delhi Air Quality Monitoring Dataset (Hourly, 2023–2026)`
- **Subtitle:** `Hourly CAAQMS multi-pollutant, meteorology, and official AQI observations across 7 Delhi monitoring stations.`
- **Tags:** `air-quality`, `pollution`, `delhi`, `india`, `time-series`, `environment`, `pm25`, `pm10`, `aqi`, `weather`

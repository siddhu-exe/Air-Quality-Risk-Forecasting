# Data

The raw dataset is 105 CPCB and DPCC spreadsheets for 7 stations (2023–2026). The ETL standardises headers, converts
pollutants to common units (µg/m³, mg/m³) and normalises timestamps to ISO 8601 in Asia/Kolkata (`UTC+05:30`). Sensor error
sentinels (e.g. `-999`) are nullified per parameter and logged in `qc_flags`, so valid concurrent measurements survive.

A cleaned public copy is on Kaggle: **[Delhi Air Quality Monitoring Dataset (2023–2026)](https://www.kaggle.com/datasets/siddharthdongardive/delhi-air-quality-monitoring-dataset-2023-2026)**
(220,042 hourly records; `caaqms_hourly.csv`, `aqi_hourly.csv`, `stations.csv`, `source_files.csv`, `column_metadata.csv`;
CAAQMS data Jan 2023 – Aug 2026, official AQI for full-year 2025; internal IDs and local paths stripped).

<details>
<summary><b>Database schema (PostgreSQL 16)</b></summary>

```text
stations (station_id PK) ──1:N──► source_files (source_file_id PK, station_id FK, filename, ...)
    │ 1:N                              │ 1:N
    ▼                                  ▼
caaqms_hourly / aqi_hourly
    station_id FK, source_file_id FK (lineage), timestamp (TIMESTAMPTZ, Asia/Kolkata),
    pm25, pm10, no2, so2, co, o3, temp, humidity, wind_speed, qc_flags, ...
    UNIQUE(station_id, timestamp)  →  idempotent ON CONFLICT DO UPDATE loading
```

- **Source lineage:** every measurement references its raw file and ingestion batch.
- **Idempotent ingestion:** the unique constraint prevents duplicates and lets corrections update in place.
- **Non-destructive QC:** only the damaged channel is nulled, with a JSON flag.

Schema DDL is in `sql/` (numbered, apply in order). Credentials come from `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`).
</details>

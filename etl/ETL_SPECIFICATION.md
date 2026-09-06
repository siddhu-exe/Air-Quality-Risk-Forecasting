# ETL Specification: Air Quality Risk Forecasting

This document specifies the Extract, Transform, Load (ETL) architecture for the Delhi Air Quality datasets.

## 1. Pipeline Stages

The pipeline follows a robust, idempotent architecture:

1. **Discovery**: Scan the raw data root for `.csv` (CAAQMS) and `.xlsx` (AQI) files.
2. **Staging**: Read raw files into pandas DataFrames. 
   - Retain raw column names.
   - For AQI files (wide format), melt/unpivot immediately to long format `(Date, Hour, Value)` in staging.
3. **Standardization (Mapping)**: 
   - Map raw column names to canonical names using the explicitly defined dictionary (Section 2).
   - Normalize station names (remove trailing whitespace/tabs).
   - Parse timestamps into `Asia/Kolkata` tz-aware datetime objects. Drop invalid epoch dates (`1970-01-01`).
4. **Validation (Quality Checks)**:
   - Identify and replace known sentinel values (e.g., `-999`, `999`, `9999`) with `NULL`.
   - Apply domain/range bounding rules (e.g., `0 <= RH <= 100`) and set physically invalid measurements to `NULL`.
5. **Load (PostgreSQL - Dry Run Mode Supported)**:
   - Perform UPSERTs based on primary composite keys `(station_id, ts)` ensures idempotency.
   - Track file lineage into `source_files` table.

## 2. Column Mapping Specification

| Raw Column Name Observed | Canonical Target Column | Target Data Type |
|--------------------------|-------------------------|------------------|
| `Timestamp`              | `ts`                    | TIMESTAMPTZ      |
| `Date`                   | *Used as base for ts in AQI* | DATE             |
| `PM2.5 (µg/m³)`       | `pm25`                  | NUMERIC(8,2)     |
| `PM10 (µg/m³)`          | `pm10`                  | NUMERIC(8,2)     |
| `NO (µg/m³)`            | `no_ugm3`               | NUMERIC(8,2)     |
| `NO2 (µg/m³)`           | `no2_ugm3`              | NUMERIC(8,2)     |
| `NOx (ppb)`              | `nox_ppb`               | NUMERIC(8,2)     |
| `NH3 (µg/m³)`           | `nh3_ugm3`              | NUMERIC(8,2)     |
| `SO2 (µg/m³)`           | `so2_ugm3`              | NUMERIC(8,2)     |
| `CO (mg/m³)`            | `co_mgm3`               | NUMERIC(8,4)     |
| `Ozone (µg/m³)`         | `ozone_ugm3`            | NUMERIC(8,2)     |
| `Benzene (µg/m³)`       | `benzene_ugm3`          | NUMERIC(8,4)     |
| `Toluene (µg/m³)`       | `toluene_ugm3`          | NUMERIC(8,4)     |
| `Xylene (µg/m³)`        | `xylene_ugm3`           | NUMERIC(8,4)     |
| `O Xylene (µg/m³)`      | `o_xylene_ugm3`         | NUMERIC(8,4)     |
| `Eth-Benzene (µg/m³)`   | `eth_benzene_ugm3`      | NUMERIC(8,4)     |
| `MP-Xylene (µg/m³)`     | `mp_xylene_ugm3`        | NUMERIC(8,4)     |
| `AT (°C)`                | `temp_c`                | NUMERIC(6,2)     |
| `RH (%)`                 | `rh_pct`                | NUMERIC(6,2)     |
| `WS (m/s)`               | `ws_ms`                 | NUMERIC(6,2)     |
| `WD (deg)`               | `wd_deg`                | NUMERIC(6,2)     |
| `RF (mm)`                | `rf_mm`                 | NUMERIC(6,2)     |
| `TOT-RF (mm)`            | `tot_rf_mm`             | NUMERIC(6,2)     |
| `SR (W/mt2)`             | `sr_wm2`                | NUMERIC(8,2)     |
| `BP (mmHg)`              | `bp_mmhg`               | NUMERIC(8,2)     |
| `VWS (m/s)`              | `vws_ms`                | NUMERIC(6,2)     |

**AQI Unpivoting mapping:**
For `.xlsx` files:
Columns like `00:00:00`, `01:00:00`, ... `23:00:00` contain the AQI observation. 
- Row's `Date` + Column header `HH:MM:SS` -> Canonical `ts`.
- Sub-cells inside -> mapped to `aqi` column.

## 3. Data-Quality Rules

### A. Timestamp Rules
- Target Timezone: `Asia/Kolkata`
- All invalid timestamps (e.g. `1970-01-01`) must be dropped.
- Detect exact duplicate `(station_id, ts)` pairs inside the same load file and drop the trailing duplicate.

### B. Sentinel Value Rules
Values exact-matching the following set must be converted to `NULL`:
`{99, -99, 999, -999, 9999, -9999, 9, -9, 0}`
*(Note: '0' is evaluated critically. 0 rainfall is valid; 0 AQI is invalid. We will target sentinels mainly at extreme limits.)*
**Specific target sentinels:** `-999, -99, 999, 9999`

### C. Physically Invalid Ranges
- `rh_pct`: `0 <= value <= 100`
- `wd_deg`: `0 <= value <= 360`
- All Pollutants (PM, Gases): `value >= 0` (No negative concentrations allowed). 
If a value falls out of this range (after filtering sentinels), replace with `NULL`.

### D. Station Normalization
Raw folders contain names like `"Jahangirpuri, Delhi - DPCC\t"`. 
- Trim all leading/trailing whitespace (`.strip()`).
- Store the cleaned representation in `station_name`.
- Retain the raw folder name in `station_folder` for mapping purposes.

### E. Idempotency & Overlap Handling
- During Database UPSERT: Use `ON CONFLICT (station_id, ts) DO UPDATE` to overwrite existing old records with newly processed (and presumably corrected or overlapping) records. The latest processed file wins.

## 4. PostgreSQL Implementation Plan

### A. stations
```sql
CREATE TABLE IF NOT EXISTS stations (
    station_id      SERIAL PRIMARY KEY,
    station_name    TEXT NOT NULL UNIQUE,
    station_folder  TEXT,
    city            TEXT,
    operator        TEXT,
    data_from       DATE,
    data_to         DATE
);
```

### B. source_files
```sql
CREATE TABLE IF NOT EXISTS source_files (
    source_file_id  SERIAL PRIMARY KEY,
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL UNIQUE,
    source_type     TEXT NOT NULL, -- 'CAAQMS' or 'AQI'
    station_id      INT REFERENCES stations(station_id),
    file_format     TEXT,
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    file_row_count  INT,
    loaded_at       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    processing_status TEXT, 
    processing_error  TEXT
);
```

### C. caaqms_hourly
```sql
CREATE TABLE IF NOT EXISTS caaqms_hourly (
    id              BIGSERIAL PRIMARY KEY,
    station_id      INT REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,
    pm25            NUMERIC(8,2),
    pm10            NUMERIC(8,2),
    no_ugm3         NUMERIC(8,2),
    no2_ugm3        NUMERIC(8,2),
    nox_ppb         NUMERIC(8,2),
    nh3_ugm3        NUMERIC(8,2),
    so2_ugm3        NUMERIC(8,2),
    co_mgm3         NUMERIC(8,4),
    ozone_ugm3      NUMERIC(8,2),
    benzene_ugm3    NUMERIC(8,4),
    toluene_ugm3    NUMERIC(8,4),
    xylene_ugm3     NUMERIC(8,4),
    o_xylene_ugm3   NUMERIC(8,4),
    eth_benzene_ugm3 NUMERIC(8,4),
    mp_xylene_ugm3  NUMERIC(8,4),
    temp_c          NUMERIC(6,2),
    rh_pct          NUMERIC(6,2),
    ws_ms           NUMERIC(6,2),
    wd_deg          NUMERIC(6,2),
    rf_mm           NUMERIC(6,2),
    tot_rf_mm       NUMERIC(6,2),
    sr_wm2          NUMERIC(8,2),
    bp_mmhg         NUMERIC(8,2),
    vws_ms          NUMERIC(6,2),
    source_file_id  INT REFERENCES source_files(source_file_id),
    UNIQUE (station_id, ts)
);
CREATE INDEX IF NOT EXISTS idx_caaqms_ts ON caaqms_hourly (ts);
```

### D. aqi_hourly
```sql
CREATE TABLE IF NOT EXISTS aqi_hourly (
    id              BIGSERIAL PRIMARY KEY,
    station_id      INT REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,
    aqi             NUMERIC(6,1),
    source_file_id  INT REFERENCES source_files(source_file_id),
    UNIQUE (station_id, ts)
);
CREATE INDEX IF NOT EXISTS idx_aqi_ts ON aqi_hourly (ts);
```

## 5. Dry Run Strategy
The Python script will execute in `--dry-run` by default. Using dry run:
1. It validates and parses all files.
2. It aggregates a report showing total expected row inserts, sentinel replacements, and invalidations.
3. No psycopg2/SQLAlchemy calls to modify data are committed; everything is rolled back or just printed as insert stubs.
# Air Quality Risk Forecasting

This repository houses the raw data and data engineering pipeline for the **Air Quality Risk Forecasting** project. It contains continuous monitoring and AQI datasets primarily focused on two major Indian cities (Delhi and Mumbai) spanning from 2023 through 2026.

## 🚀 Project Overview

The core objective of this phase of the project is to safely parse, standardize, and load scattered raw air quality sensor data (both continuous `.csv` outputs and wide-format `.xlsx` hour-level files) into a relational PostgreSQL database schema.

### Core Features Installed So Far
1. **Automated Data Profiler**: A 100% read-only recursive scanner that checks for schema consistency, missingness, sentinel faults, and uncovers unique structures inside `.xlsx` documents.
2. **Idempotent ETL Pipeline**: A robust pipeline equipped with dry-run capabilities that maps non-standard features onto a canonical schema, sanitizes out-of-bounds physical properties (e.g., negative wind speeds), strips sentinels, and transforms wide AQI grids into standard relational row inserts.
3. **Reproducible Schema DDLs**: Fully prepared PostgreSQL definitions for monitoring stations, dataset files lineage, and specific pollutant matrices ensuring data reliability.

---

## 📁 Repository Structure

```text
.
├── CLAUDE.md                   # AI Assistant / Workspace guidance rules
├── etl/                        # Pipeline execution logic
│   ├── discover.py             # File discovery and metadata reading
│   ├── generate_mapping_report.py # Automated mapping reports
│   ├── load_postgres.py        # Database adapters (UPSERT actions)
│   ├── pipeline.py             # Main Orchestrator (execute this!)
│   ├── schemas.py              # Canonical constants and bounds
│   ├── transform_aqi.py        # Openpyxl XLSX unpivoting
│   ├── transform_caaqms.py     # Pandas read algorithms for Raw CSVs 
│   └── validation.py           # Integrity checking (sentinels / bounds)
├── Og Data/                    # Raw data (Organized by City -> Station)
│   ├── Delhi data/
│   └── Mumbai data/
├── profiling/                  # Generated discovery reports 
│   ├── profile_raw_data.py     # Automated read-only schema discovery scanner
│   ├── profiling_summary.md    # Actionable 14-point narrative
│   └── ...                     # (Other schema / gap finding CSVs)
├── reports/                    # Output from validation & ETL mapping routines
│   └── column_mapping_report.md
└── sql/                        # Target database structural definitions
    ├── 001_create_schema.sql
    ├── 002_create_tables.sql
    └── 003_indexes.sql
```

---

## 🛠️ Setup & Installation

**Prerequisites:**
- Python 3.9+
- A working PostgreSQL database installation (for future load steps)

**1. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**2. Install dependencies**
```bash
pip install pandas numpy openpyxl
```

---

## 🏃 Usage

### 1. Run Data Discovery Profiling
To thoroughly audit the source files cleanly without modifying them:
```bash
python3 profiling/profile_raw_data.py
```
*Outputs are saved recursively to the `profiling/` directory.*

### 2. Verify Data Mappings
To confirm all recognized raw files have matching schemas inside the Canonical Database schema:
```bash
python3 etl/generate_mapping_report.py
```

### 3. Run the ETL Pipeline (Dry Run)
Execute the ETL logic safely to see what would be updated or stripped out before touching the Production Database.
```bash
python3 etl/pipeline.py --dry-run
```

---

## 🛡️ Architecture & Rules
We operate strictly under these principles:
- **Never modify raw files**: Any cleanup runs *in-memory* or outputs to the `reports/` folder.
- **Idempotency first**: Database inserts utilize unique composite keys `(station_id, ts)` leveraging Postgres `ON CONFLICT DO UPDATE`. You may run the pipeline continuously without producing duplicate telemetry.
- **Timezone Awareness**: Timestamps are parsed uniformly into `Asia/Kolkata` Timezones and validated to filter out default epoch glitches (`1970-01-01`).

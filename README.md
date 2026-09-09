# Air Quality Risk Forecasting

This repository houses the raw data and data engineering pipeline for the **Air Quality Risk Forecasting** project. It contains continuous monitoring and AQI datasets primarily focused on two major Indian cities (Delhi and Mumbai) spanning from 2023 through 2026.

## 🚀 Project Overview

The project has now successfully completed Phase 4 (Exploratory Data Analysis). Scattered raw air quality sensor data (COVID & post-COVID continuous `.csv` outputs and wide-format `.xlsx` AQI files) are automatically parsed, standardized, and loaded into an idempotent PostgreSQL database schema. We have subsequently generated a comprehensive statistical and visual profile of the data.

### Core Features Installed So Far
1. **Automated Data Profiler**: A 100% read-only recursive scanner that checks for schema consistency, missingness, sentinel faults, and uncovers unique structures inside `.xlsx` documents.
2. **Idempotent ETL Pipeline**: A robust pipeline that maps non-standard features onto a canonical schema, sanitizes out-of-bounds physical properties, strips sentinels, and transforms wide AQI grids into standard relational row inserts. Connects to Postgres using `psycopg2` `execute_values` for high-throughput batch upserts with perfect idempotency.
3. **Production Database & Architecture**: Local PostgreSQL cluster configuration, comprehensive schemas with explicit foreign key constraints (`ON DELETE RESTRICT`), validation data checks, and automated backups (`pg_dump`). Fully populated with 105 raw files resulting in ~162K hourly pollution records and ~57K AQI rows for Delhi.
4. **Exploratory Data Analysis (EDA)**: A comprehensive SQL-first statistical analysis generating 11 publication-quality visualizations and deep metric evaluations (spatial correlation, pollutant dynamics, missingness profiles, autocorrelation, severe episode tracking) to guide Phase 5 forecasting.

---

## 📁 Repository Structure

```text
.
├── CLAUDE.md                   # AI Assistant / Workspace guidance rules
├── backups/                    # Database pg_dump binary backups
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
├── reports/                    # Output from validation, mapping, & EDA routines
│   ├── column_mapping_report.md
│   └── eda/                    # Phase 4 EDA outputs
│       ├── EDA_REPORT.md       # Comprehensive 12-section statistical report
│       ├── figures/            # 11 Publication-quality visualizations (.png)
│       └── *.csv               # Statistical summary tables & metrics
├── src/                        # Analysis and processing source code
│   └── eda/                    # Modular EDA analysis & visualization scripts
│       ├── data_health_and_coverage.py
│       ├── temporal_and_station_analysis.py
│       ├── advanced_statistical_analysis.py
│       └── generate_visualizations.py
├── local_pg_data/              # Local PostgreSQL 16 cluster data directory (port 5433)
└── sql/                        # Target database structural definitions
    ├── 001_create_tables.sql
    ├── 002_constraints.sql
    ├── 003_indexes.sql
    ├── 004_validation_schema.sql
    └── 005_validation_data.sql
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
pip install -r requirements.txt
```

**3. Database Configuration**
Create a `.env` file at the root tracking the DB credentials:
```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=air_quality_db
POSTGRES_USER=aq_admin
POSTGRES_PASSWORD=your_secure_password
```
Start your PostgreSQL server instance on the matching port.

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

### 3. Run the Production ETL Pipeline
Execute the ETL logic safely to load data into the Production Database seamlessly tracking source lineage and idempotency.
```bash
# Small controlled load (Anand Vihar, Jan 2025)
python3 etl/run_small_load.py

# Full production load (All Delhi 105 files)
python3 etl/run_full_load.py
```

### 4. Database Validation
Re-verify total counts, missing hours, and absolute duplication logic constraints.
```bash
python3 verify_full_load.py
```

### 5. Generate Exploratory Data Analysis (EDA)
To re-run the statistical analysis suite and rebuild the 11 visualizations:
```bash
python3 src/eda/data_health_and_coverage.py
python3 src/eda/temporal_and_station_analysis.py
python3 src/eda/advanced_statistical_analysis.py
python3 src/eda/generate_visualizations.py
```

---

## 🛡️ Architecture & Rules
We operate strictly under these principles:
- **Never modify raw files**: Any cleanup runs *in-memory* or outputs to the `reports/` folder.
- **Idempotency first**: Database inserts utilize unique composite keys `(station_id, ts)` leveraging Postgres `ON CONFLICT DO UPDATE`. You may run the pipeline continuously without producing duplicate telemetry.
- **Timezone Awareness**: Timestamps are parsed uniformly into `Asia/Kolkata` Timezones and validated to filter out default epoch glitches (`1970-01-01`).

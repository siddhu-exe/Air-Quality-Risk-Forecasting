# Air Quality Risk Forecasting

This repository houses the raw data and data engineering pipeline for the **Air Quality Risk Forecasting** project. It contains continuous monitoring and AQI datasets primarily focused on two major Indian cities (Delhi and Mumbai) spanning from 2023 through 2026.

## 🚀 Project Overview

The project has completed **Phase 1–3 (ETL & Database Ingestion)**, **Phase 4 (Exploratory Data Analysis)**, **Phase 5 (Feature Engineering & Baseline Modeling)**, and **Phase 6 / 6B (Multi-Horizon Forecasting & 24h Optimization Suite)**. Scattered raw air quality sensor data (continuous `.csv` outputs and wide-format `.xlsx` AQI files) are automatically parsed, standardized, and loaded into an idempotent PostgreSQL database schema. A comprehensive 124-feature tabular dataset across 7 feature groups has been constructed with zero temporal leakage, future forecasting targets ($h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$) audited, versioned ML datasets exported with SHA-256 integrity checksums, and multi-horizon models (LightGBM Tuned and Regularized Hybrid Persistence Ensembles) deployed and verified across all 7 Delhi stations.

### Core Features Installed So Far
1. **Automated Data Profiler**: A 100% read-only recursive scanner that checks for schema consistency, missingness, sentinel faults, and uncovers unique structures inside `.xlsx` documents.
2. **Idempotent ETL Pipeline**: A robust pipeline that maps non-standard features onto a canonical schema, sanitizes out-of-bounds physical properties, strips sentinels, and transforms wide AQI grids into standard relational row inserts. Connects to Postgres using `psycopg2` `execute_values` for high-throughput batch upserts with perfect idempotency.
3. **Production Database & Architecture**: Local PostgreSQL cluster configuration, comprehensive schemas with explicit foreign key constraints (`ON DELETE RESTRICT`), validation data checks, and automated backups (`pg_dump`). Fully populated with 105 raw files resulting in ~162K hourly pollution records and ~58K AQI rows for Delhi.
4. **Exploratory Data Analysis (EDA)**: A comprehensive SQL-first statistical analysis generating 11 publication-quality visualizations and deep metric evaluations (spatial correlation, pollutant dynamics, missingness profiles, autocorrelation, severe episode tracking) to guide forecasting.
5. **Feature Engineering & Baseline Modeling**: A leakage-safe tabular pipeline constructing 124 features across 7 groups (AQI lags, pollutant lags, causal rolling statistics, cyclical temporal features, IMD seasonality, meteorology, and leave-one-out spatial network features). Benchmarks Naive, Seasonal, and Moving Average baselines and ranks feature predictive power across 1h, 6h, and 24h horizons.
6. **Multi-Horizon Forecasting & 24h Failure Optimization (Phase 6 / 6B)**: Full multi-horizon benchmarking (1h LightGBM MAE = 2.29, 6h LightGBM MAE = 11.84, 24h Hybrid MAE = 35.48) with dedicated Google Colab training suites (`notebooks/phase_6_colab_training.ipynb`, `notebooks/phase_6b_24h_optimization.ipynb`), exhaustive mathematical failure diagnostics (tree extrapolation ceilings, non-stationary temporal traps, delta formulations), and serialization of production model weights.

---

## 📁 Repository Structure

```text
.
├── CLAUDE.md                   # AI Assistant / Workspace guidance rules
├── backups/                    # Database pg_dump binary backups
├── data/
│   └── processed/
│       ├── features_2025.parquet # Clean 124-feature tabular matrix (57,946 rows)
│       └── ml/                 # Versioned ML Parquet datasets & metadata JSONs
│           ├── air_quality_ml_1h_v1.parquet (.json)
│           ├── air_quality_ml_6h_v1.parquet (.json)
│           └── air_quality_ml_24h_v1.parquet (.json)
├── docs/                       # Project documentation, timelines, and findings
│   ├── overview.md
│   ├── technical_timeline.md
│   ├── simple_timeline.md
│   ├── eda_findings.md
│   ├── baseline_findings.md    # Phase 5 Baseline & Feature findings
│   ├── phase_6_training.md     # Phase 6 Colab ML Training Guide
│   ├── phase_6b_findings.md    # Phase 6B 24h Failure & Optimization findings
│   └── llm_context.md
├── etl/                        # Pipeline execution logic
│   ├── discover.py             # File discovery and metadata reading
│   ├── generate_mapping_report.py # Automated mapping reports
│   ├── load_postgres.py        # Database adapters (UPSERT actions)
│   ├── pipeline.py             # Main Orchestrator (execute this!)
│   ├── schemas.py              # Canonical constants and bounds
│   ├── transform_aqi.py        # Openpyxl XLSX unpivoting
│   ├── transform_caaqms.py     # Pandas read algorithms for Raw CSVs 
│   └── validation.py           # Integrity checking (sentinels / bounds)
├── notebooks/                  # Interactive experimentation & Cloud Training
│   ├── phase_6_colab_training.ipynb # 16-section Google Colab Multi-Horizon Training Notebook
│   └── phase_6b_24h_optimization.ipynb # 12-section Google Colab 24h Optimization Notebook
├── models/                     # Serialized production model artifacts
│   ├── 1h/                     # 1-Hour LightGBM model pipeline
│   ├── 6h/                     # 6-Hour LightGBM model pipeline
│   └── 24h/                    # 24-Hour Ridge & Hybrid model pipelines
├── Og Data/                    # Raw data (Organized by City -> Station)
│   ├── Delhi data/
│   └── Mumbai data/
├── phase_5/                    # Phase 5 formal specifications & audits
│   ├── target_definition.md    # Target formulation & horizon availability
│   ├── feature_specification.md# 124-feature schema & definitions
│   ├── leakage_audit.md        # Zero-leakage mathematical audit
│   ├── split_strategy.md       # Chronological split documentation
│   └── experiments.md          # Baseline evaluation matrix & feature rankings
├── profiling/                  # Generated discovery reports 
│   ├── profile_raw_data.py     # Automated read-only schema discovery scanner
│   ├── profiling_summary.md    # Actionable 14-point narrative
│   └── ...                     # (Other schema / gap finding CSVs)
├── reports/                    # Output from validation, mapping, EDA, & Modeling
│   ├── column_mapping_report.md
│   ├── eda/                    # Phase 4 EDA outputs (11 figures, EDA report)
│   ├── features/               # Feature manifest & target availability CSVs
│   └── modeling/               # Baseline benchmarks & feature rankings
│       ├── baselines.csv       # Heuristic & ML baseline metrics
│       ├── feature_importance.csv # Ranked feature correlations
│       ├── ml_dataset_manifest.csv # Cryptographic SHA-256 ML dataset manifest
│       ├── PHASE_5_BASELINE_REPORT.md # Comprehensive Phase 5 report
│       ├── 24h/                # Phase 6B 24h failure diagnostics & benchmarks
│       │   ├── 24h_failure_audit.csv
│       │   ├── 24h_distribution_shift.csv
│       │   ├── 24h_error_analysis.csv
│       │   ├── 24h_feature_ablation.csv
│       │   └── 24h_optimization_results.csv
│       └── PHASE_6B_24H_REPORT.md # Comprehensive Phase 6B 24h optimization report
├── scripts/                    # Maintenance & generator utilities
│   ├── generate_colab_notebook.py # Builds phase_6_colab_training.ipynb
│   └── generate_phase_6b_notebook.py # Builds phase_6b_24h_optimization.ipynb
├── src/                        # Analysis and modeling source code
│   ├── eda/                    # Modular EDA analysis & visualization scripts
│   ├── features/               # Feature engineering & dataset export
│   │   ├── build_features.py   # 124-feature causal transformer
│   │   ├── export_ml_datasets.py # Horizon Parquet & manifest exporter
│   │   └── target_analysis.py  # Target coverage & availability audit
│   └── models/                 # Forecasting models & evaluation suites
│       ├── evaluate.py         # Standardized metrics (MAE, RMSE, R², Extreme MAE)
│       ├── baselines.py        # Heuristic baseline benchmark suite
│       └── feature_analysis.py # Feature correlation & group ranking engine
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

### 6. Run Feature Engineering & Baseline Benchmarks
To build the 124-feature dataset, evaluate heuristic baselines, and compute feature importance rankings:
```bash
# Audit target availability across stations and horizons (1h, 6h, 24h)
python3 src/features/target_analysis.py

# Construct 124 causal features (saved to data/processed/features_2025.parquet)
python3 src/features/build_features.py

# Evaluate Naive, Seasonal, and Moving Average baselines across all splits
python3 src/models/baselines.py

# Compute feature predictive correlations and group rankings
python3 src/models/feature_analysis.py
```

### 7. Export Versioned ML Datasets & Run Cloud ML Training (Phase 6)
To export reproducible Parquet datasets with SHA-256 checksums and execute model training in Google Colab:
```bash
# Export versioned datasets for 1h, 6h, and 24h horizons (data/processed/ml/)
python3 src/features/export_ml_datasets.py --version v1

# Re-generate Colab notebook if generator script is updated
python3 scripts/generate_colab_notebook.py
```
Open `notebooks/phase_6_colab_training.ipynb` in [Google Colab](https://colab.research.google.com), upload the desired dataset from `data/processed/ml/`, and execute end-to-end model training, hyperparameter optimization, and evaluation.

---

## 🛡️ Architecture & Rules
We operate strictly under these principles:
- **Never modify raw files**: Any cleanup runs *in-memory* or outputs to the `reports/` folder.
- **Idempotency first**: Database inserts utilize unique composite keys `(station_id, ts)` leveraging Postgres `ON CONFLICT DO UPDATE`. You may run the pipeline continuously without producing duplicate telemetry.
- **Timezone Awareness**: Timestamps are parsed uniformly into `Asia/Kolkata` Timezones and validated to filter out default epoch glitches (`1970-01-01`).

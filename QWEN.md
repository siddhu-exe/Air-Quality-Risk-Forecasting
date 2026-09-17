# QWEN.md — Air Quality Risk Forecasting

Instructional context for AI assistants working in this repository. Read this before making changes.

## Project Overview

An end-to-end air-quality risk forecasting system that maps raw Indian government sensor data (CAAQMS pollutant CSVs + AQI Excel logs) to actionable policy alerts, expressed as **CPCB risk tiers** (6 classes) and **CAQM GRAP emergency stages** (I–IV).

This is a portfolio-quality **data engineering + data science** lifecycle, not just model training. It spans profiling, schema normalisation, an idempotent PostgreSQL ETL, causal feature engineering, multi-horizon forecasting (`h ∈ {1h, 6h, 24h}`), and deterministic risk classification.

* **Primary scope:** Delhi — 7 DPCC/CPCB monitoring stations (Anand Vihar, Bawana, Dwarka-Sector 8, ITO, Jahangirpuri, Punjabi Bagh, R K Puram), 2023–2026.
* **Secondary scope:** Mumbai — city-level AQI only (Jan–Jul 2026). **Never mix Mumbai into the Delhi dataset**; it is reserved for external validation.
* **Data quality focus:** the hard test is the Nov–Dec 2025 peak winter pollution crisis split.

### Pipeline

```text
RAW GOVERNMENT DATA → POSTGRESQL (idempotent ETL) → VALIDATION →
EDA → FEATURE ENGINEERING → BASELINE BENCHMARKING → VERSIONED ML DATASETS →
MULTI-HORIZON FORECASTING → CPCB RISK CLASSIFICATION → (Phase 8: serving/dashboard)
```

## Current Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1–3 | ETL, data-quality hardening, idempotent PostgreSQL ingestion | Complete |
| 4 | EDA, statistical profiling, 11-figure visual suite | Complete |
| 5 | 124 causal features, leakage audit, baseline benchmarking | Complete |
| 6 / 6B / 6C | Multi-horizon forecasting + 24h failure analysis & refinement | Complete |
| 7 | CPCB risk classification + GRAP alerting + episode lead-time audit | Complete |
| **8** | **Production deployment, real-time inference, REST API, dashboard, alerting** | **Scheduled** |

### Validated out-of-sample results (Nov–Dec 2025 winter test split)

| Horizon | Model | MAE | R² | Naive persistence MAE |
|---------|-------|-----|-----|------------------------|
| 1h | Tuned LightGBM | 2.29 | 0.9958 | 2.40 |
| 6h | Tuned LightGBM | 11.84 | 0.9126 | 14.73 |
| 24h | 50/50 Hybrid Persistence + Ridge (α=1000) | 34.11 | 0.3647 | 38.34 |

Classification (Phase 7): Macro F1 / Severe Recall / Critical Miss Rate = 0.9446 / 98.36% / 0.000% (1h), 0.6565 / 83.18% / 0.000% (6h), 0.3386 / 61.08% / 0.000% (24h). The 24h model gives 17.36h mean advance warning on Severe episodes (74.4% hit rate).

## Tech Stack

* **Language:** Python 3.12 (3.9+ supported)
* **Data:** `pandas` 2.1.4, `numpy` 1.26.4, `pyarrow` (Parquet, Snappy), `openpyxl` (XLSX)
* **DB:** PostgreSQL 16, native user-space cluster via `initdb` in `local_pg_data/`, **port 5433**, accessed with `psycopg2` (no ORM)
* **ML:** `scikit-learn`, `xgboost`; LightGBM/Optuna used in the Google Colab notebooks (not in `requirements.txt`)
* **Viz/EDA:** `matplotlib`, `seaborn`, `plotly`; dashboard dependency (`streamlit`) pre-staged for Phase 8
* **Config:** `python-dotenv`; credentials live only in `.env` (gitignored)
* **Training split:** heavy model training is intentionally offloaded to Google Colab notebooks. Local machine has **no GPU and no Docker** — local work must stay vectorized/lightweight.

## Repository Map

```text
.
├── CLAUDE.md                     # Older assistant guidance (superseded by this file)
├── README.md                     # Public-facing project summary
├── requirements.txt              # Phase-tagged Python dependencies
├── .env                          # DB credentials (gitignored — never commit)
├── verify_full_load.py           # Post-load DB integrity validation
├── test_db.sh                    # Migration + constraint smoke test (shell)
├── test_aqi_ts.py / test_aqi_ts2.py / test_bp.py  # Ad-hoc ETL sanity scripts
├── data/
│   ├── Artifacts/{1h,6h,24h}/    # Model joblib, predictions parquet, diagrams, eval CSVs
│   └── processed/
│       ├── features_2025.parquet # Clean 124-feature matrix (57,946 rows)
│       └── ml/                   # Versioned ML parquet datasets + metadata JSONs (v1)
├── db/migrations/001_initial_schema.sql
├── docs/                         # Internal working notes: timeline, LLM context, findings
├── etl/                          # discover → transform → validate → load pipeline
├── models/                       # Serialized production artifacts (lgb_*_v1.joblib, 24h/final/)
├── notebooks/                    # Google Colab training suites (Phase 6 / 6B / 6C)
├── Og Data/                      # Raw source data — READ-ONLY, never modify/rename
├── phase_5/ , phase_7/           # Formal per-phase specifications & leakage audits
├── profiling/                    # Discovery scripts + profiling CSVs
├── reports/                      # eda/ features/ modeling/ classification/ outputs
├── scripts/                      # Generate the Colab notebooks programmatically
├── sql/                          # Canonical DDL migrations (see order below)
├── src/                          # eda/ features/ models/ analysis code
└── local_pg_data/                # Local PostgreSQL cluster data dir (gitignored)
```

## Environment Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `.env` at the repo root (never commit; keys are read by `etl/load_postgres.py::load_env`):

```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=air_quality_db
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<password>
```

## Building & Running

**Critical:** run commands **from the repository root**. `src/` scripts use project-relative paths (`Path("data/processed")`, `reports/...`), so changing directory breaks them. ETL scripts work because Python adds the script's own directory to `sys.path`, letting `etl/*.py` import siblings like `schemas`, `validation`, `discover`.

### 1. Database cluster (start / stop manually)

```bash
pg_ctl -D local_pg_data start     # boot local PostgreSQL cluster on port 5433
pg_ctl -D local_pg_data stop      # stop it (do this when not ingesting, to save battery)
```

Apply migrations in order (idempotent, `IF NOT EXISTS`-guarded). The canonical DDL is:

```bash
psql -f sql/001_create_tables.sql      # tables + PKs
psql -f sql/002_constraints.sql        # FKs + UNIQUE(station_id, timestamp)
psql -f sql/003_indexes.sql            # timestamp / source_file indexes
psql -f sql/006_fix_fk_delete_policy.sql  # rewrites FKs to ON DELETE RESTRICT (final policy)
```

`sql/001_create_schema.sql` is a no-op placeholder (default `public` schema). `sql/004_*` / `sql/005_*` are validation-only. `test_db.sh` runs migrations plus synthetic constraint tests — note it is a smoke test, run it knowingly since it inserts then deletes a synthetic station.

### 2. ETL

```bash
python3 etl/pipeline.py --dry-run       # transform-only dry run; prints yield + QC stats, no DB writes
python3 etl/run_small_load.py           # controlled load: one station, one month
python3 etl/run_full_load.py            # full production load (all Delhi files); halts on first error
python3 verify_full_load.py             # row counts, coverage, duplicate integrity checks
```

`run_full_load.py` commits **per file**, writes a manifest to `full_load_report.json`, and `sys.exit(1)` on any failure to preserve integrity. Loads are idempotent via `ON CONFLICT (station_id, timestamp) DO UPDATE`.

### 3. Feature engineering & ML dataset export

```bash
python3 src/features/target_analysis.py       # target coverage / availability
python3 src/features/build_features.py        # builds data/processed/features_2025.parquet + manifest
python3 src/features/export_ml_datasets.py --version v1   # versioned parquet in data/processed/ml/
```

### 4. Modeling & evaluation

```bash
python3 src/models/baselines.py               # heuristic baselines
python3 src/models/train_ml_baseline.py       # local baseline training
python3 src/models/feature_analysis.py        # feature ranking / group importance
python3 src/models/phase_6c_refinement.py     # 24h final refinement (writes models/24h/final/, reports/modeling/24h/final/)
python3 src/models/phase_7_classification.py  # CPCB/GRAP discretisation, metrics, episode lead-time audit
```

Phase 6/6B/6C heavy training runs in `notebooks/phase_6*_colab_training.ipynb` (regenerate via `scripts/generate_*.py`).

### 5. EDA

```bash
python3 src/eda/data_health_and_coverage.py
python3 src/eda/temporal_and_station_analysis.py
python3 src/eda/advanced_statistical_analysis.py
python3 src/eda/generate_visualizations.py
```

EDA also runs SQL-first against the live DB: CTEs, `PERCENTILE_CONT`, `EXTRACT`, window `LAG()`, `CORR()`, `REGR_SLOPE()`.

## Critical Data Invariants — DO NOT REGRESS

These encode hard-won bug fixes. Changing them silently corrupts historical data.

1. **Epoch bug:** AQI XLSX `Date` columns hold bare integers (1, 2, …). Reconstruct timestamps by extracting `YYYY` + `Month` from the **filename** via regex and concatenating with the integer (see `etl/transform_aqi.py`). Never let them coerce to 1970.
2. **Sentinel values:** only extreme structural constants (`-999`, `-9999`, `9999`) are treated as sentinels. Do **not** add `9`, `-9`, `999`, or `-99` — those are legitimate readings (`SENTINEL_VALUES` in `etl/schemas.py`).
3. **Barometric pressure bounds:** `bp_mmhg` is bounded `(400, 998.9)` because `999.0` is a sensor clip error, while genuine hPa readings sit at 966–999.
4. **Row retention:** a bad measurement nullifies **the cell**, never the row. The row is kept and a JSON warning (e.g. `{"pm25": "SENTINEL_-999"}`) is written to the row's `qc_flags` JSONB column. Continuous hourly records are preserved.
5. **Idempotency:** `UNIQUE(station_id, timestamp)` on both fact tables + `ON CONFLICT DO UPDATE`. Re-running a load must never duplicate.
6. **Timezone:** all timestamps are `TIMESTAMPTZ` localised to `Asia/Kolkata`.
7. **FK delete policy:** all FKs are `ON DELETE RESTRICT` (after `sql/006_fix_fk_delete_policy.sql`), not CASCADE — deleting a station/source file must never silently destroy observations.
8. **Raw data is immutable:** never move, rename, or rewrite `Og Data/`. Parsing relies on recursive discovery (`etl/discover.py`) and on exact filename patterns.
9. **`Jahangirpuri` folder name contains a trailing tab character** — use glob patterns or raw-string paths when scripting against it.
10. **Zero leakage:** every feature must be causal (`≤ t`). Trailing rolling windows are `[t-W+1, t]`, lags are positive shifts, and cross-station spatial aggregates use leave-one-out values at `t-1`. Audit any new feature against `phase_5/leakage_audit.md` and `phase_7/leakage_audit.md`.

## Modeling & Evaluation Conventions

* **Feature taxonomy (124 features, 7 groups):** A recent AQI lags (10) · B pollutant lags (35) · C causal trailing rolling stats (32) · D temporal/cyclical (13) · E IMD seasonality (4) · F meteorology (24) · G cross-station spatial (6). Group assignments are computed in `src/features/build_features.py::get_feature_group` and exported to `reports/features/feature_manifest.csv`.
* **Chronological 3-way split** (never shuffle): Train Jan–Aug 2025 (~65.5%), Validation Sep–Oct 2025 (~17.0%), Test Nov–Dec 2025 peak winter (~17.5%). 2024 data is the warm-up buffer.
* **24h horizon caveats:** tree models hit a **step-function extrapolation ceiling** during winter spikes; ordinal calendar features (`month`, `day_of_year`) are non-stationary and caused catastrophic mis-routing across train/test regimes. The 24h solution is deliberately a 50/50 Hybrid Persistence + Ridge (α=1000) on ~49 curated causal features — **do not replace it with a GBDT** without re-running the Phase 6C validation-first sweep.
* **Keep `src/models/evaluate.py::compute_metrics` as the single metric source** (MAE, RMSE, R², MAPE, Extreme MAE for AQI ≥ 300, directional accuracy). Don't hand-roll metric formulas elsewhere.
* **CPCB boundaries:** `[0, 51, 101, 201, 301, 401, 501]` → Good/Satisfactory/Moderate/Poor/Very Poor/Severe via `np.digitize`. **GRAP stages:** I 201–300, II 301–400, III 401–450, IV > 450 (`src/models/phase_7_classification.py`). Classification is deterministic binning of continuous predictions — no learned thresholds and no cost-aware threshold shifting (a documented limitation).

## Coding Conventions

* **Pipeline module layout:** ETL follows `discover → transform_* → validation → load_postgres`, orchestrated by `pipeline.py` / `run_*_load.py`. Each transform returns `(df, stats_dict)` and signals failure with `stats["status"] == "error"` rather than raising.
* **Style:** plain functions and dicts, module-level constants, type hints on public signatures (`tuple[pd.DataFrame | None, dict]`), `from __future__ import annotations` in newer files. No classes/ORM. Comments explain *why* (e.g. the epoch bug), so preserve existing rationale comments.
* **Column naming:** ETL layer uses canonical short names (`pm25`, `no_ugm3`, `ts`); DB columns use ERD names (`pm25`, `no`, `timestamp`). The bridge is `CAAQMS_COL_MAP` / `AQI_COL_MAP` in `etl/load_postgres.py`. Unmapped ETL columns are intentionally dropped.
* **Secrets:** never hard-code credentials. `etl/load_postgres.py` reads strictly from `.env`. (`src/features/build_features.py` has fallback defaults; prefer exporting env vars or loading `.env` when running it.)
* **Paths:** prefer `Path(__file__).resolve().parent` anchors for ETL; note that `src/` analysis scripts assume CWD = repo root.
* **Analysis-first phases:** each phase has a formal spec directory (`phase_5/`, `phase_7/`) with `target_definition.md`, `leakage_audit.md`, and an evaluation/split strategy. New phases should follow this pattern and produce a formal report in `reports/`.
* **Reports vs docs:** `reports/` holds generated evidence (CSVs, parquet, figures, audit markdown); `docs/` holds hand-written internal working notes (timeline, context, findings).

## Testing & Verification

There is **no pytest suite**; verification is script-based and data-driven.

* `python3 verify_full_load.py` — the primary DB integrity gate (row counts, per-station coverage, duplicate check).
* `bash test_db.sh` — migration + UNIQUE-constraint smoke test (inserts/deletes a synthetic station).
* `test_aqi_ts.py`, `test_aqi_ts2.py`, `test_bp.py` — ad-hoc transform/sanity probes (hard-coded paths, run from root).
* Phase gates are enforced by formal reports: `reports/modeling/PHASE_5_BASELINE_REPORT.md`, `PHASE_6C_24H_FINAL_REPORT.md`, `reports/eda/EDA_REPORT.md`, `reports/classification/PHASE_7_FINAL_AUDIT.md`.

**Before claiming a change works:** run the relevant script and the applicable validation gate above. If you cannot run it (e.g. DB not started), say so explicitly rather than asserting success.

## Phase 8 Roadmap (next work)

1. **Real-time inference engine** — consume newly ingested hourly data, rebuild the causal feature vector, invoke the 1h/6h LightGBM + 24h hybrid models, assign CPCB/GRAP tiers.
2. **REST API** — FastAPI endpoints (`/api/v1/stations`, `/forecast/{station_id}`, `/alerts/grap`, `/health`).
3. **Interactive dashboard** — geospatial Delhi AQI map, multi-horizon trend charts, risk-tier distributions, active GRAP advisories (Streamlit/Plotly already in `requirements.txt`).
4. **Alert dispatcher** — webhooks on projected GRAP Stage III/IV crossings.

## Known Limitations (documented, not bugs)

* Modest 24h skill (R² ≈ 0.36) — real but limited variance explained.
* No cost-aware threshold tuning for precision/recall trade-offs.
* Causal scope excludes external policy interventions and point-source emission modelling.

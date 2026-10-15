# Architecture

Delhi air-quality risk forecasting: 1h / 6h / 24h AQI forecasts for seven CAAQMS stations, CPCB/GRAP risk classes, and a live
pipeline that scores hash-pinned models inside scheduled jobs. No number below is a result; every metric lives in a generated
table (`reports/metrics/headline_metrics.csv`, `docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`).

## System overview

```
 OpenAQ / data.gov.in / (WAQI, candidate)          GitHub Actions cron (hourly)
            |                                     ingest.yml        forecast.yml        score.yml (planned)
            v                                          |                 |                    |
   src/live/sources  --QC--> Supabase Postgres (schema aq) <-- joblib inference in the job --+
                                      |
                                      v
                         FastAPI on Azure Container Apps  (/api/v1, scale to zero, GHCR image)
                                      |
                                      v
                           React frontend on Vercel
```

- **No model server.** Inference runs inside the forecast job; the API only reads stored forecasts.
- **Training is offline** (Colab). Nothing in CI or the API trains a model.
- **Secrets** live only in environment variables, GitHub secrets and Azure; `DATABASE_URL` (job, read-write) and
  `DATABASE_URL_READONLY` (API) are never printed.

## Layers

| Layer | Where | What it does |
| :--- | :--- | :--- |
| Raw data to Postgres | `etl/`, `sql/` | CPCB/DPCC spreadsheets in `Og Data/` are parsed, QC'd and loaded idempotently into a local PostgreSQL 16 (research copy). |
| EDA | `src/eda/` | Figures and the EDA report in `reports/eda/`. |
| Features | `src/features/` | One leakage-safe feature builder (`build_features.py`, `compute_feature_frame`) used for training and for live scoring. |
| Models | `src/models/`, `models/` | Frozen research models, and the live-consistent retrain in `models/live/`. |
| Evaluation | `src/evaluation/` | Headline metrics table, rolling-origin backtest, live audits (WAQI round trip, calibration side check). |
| Classification and causal | `src/models/phase_7_classification.py`, `src/analysis/` | CPCB tiers, GRAP stages, cost-aware thresholds, Diwali ITS analysis. |
| Live pipeline | `src/live/`, `db/migrations/`, `config/live.toml` | Source adapters, QC, AQI recompute, forecast job, parity check. |
| Serving | `backend/`, `frontend/`, `app.py` + `dashboard/` (legacy) | See `README.md`. The legacy Streamlit app and `backend/main.py` are removed when the new API lands. |

## Data and ETL rules that must hold

These were found as bugs and are enforced in `etl/`:

1. AQI spreadsheets store `Date` as a bare day number; the month comes from the file name and the timestamp is rebuilt in Asia/Kolkata.
2. Sentinel values are only the structural constants (`-999`, `-9999`, `9999`). Small values such as `9` or `-9` are real readings.
3. Barometric pressure is bounded at (400, 998.9) mmHg so genuine hPa-scale readings are kept and the `999.0` clip value is dropped.
4. A bad measurement nulls its own cell, never the row; the reason is stored in the row's `qc_flags` JSONB column.
5. Fact tables are unique on `(station_id, timestamp)` and loads use `ON CONFLICT DO UPDATE`, so a load can be repeated safely.
6. Mumbai data is not mixed into the Delhi dataset. It is reserved for external validation.

## Target and baseline

The official CPCB AQI is a 24-hour rolling average of sub-indices, so persistence is a very strong baseline (lag-1 autocorrelation
about 0.998; see `reports/eda/EDA_REPORT.md`). Every model result is reported next to persistence on the same rows, as skill
= 1 - MAE_model / MAE_persistence with day-block bootstrap intervals. The official AQI only exists for 2025; earlier years use an
AQI recomputed from raw pollutants (`src/features/compute_cpcb_aqi.py`), tagged by `aqi_source`.

Test window: 2025-11-01 .. 2025-12-31, scored once. Validation (2025-09-01 .. 2025-10-31) selects every hyper-parameter and threshold.

## Modeling decisions and why

- **1h / 6h: LightGBM** on 131 causal features (lags, trailing windows, leave-one-out network signals, station one-hots).
- **24h: 50 % persistence + 50 % Ridge (alpha 1000)** on 49 features. Trees cannot predict above the largest training AQI, which
  under-predicts winter crises badly; ordinal calendar features (month, day of year) routed winter rows into monsoon leaves and
  were removed. A regularised linear model extrapolates smoothly. Details in `reports/modeling/PHASE_6B_24H_REPORT.md` and
  `reports/modeling/PHASE_6C_24H_FINAL_REPORT.md`.
- **No 24h PM2.5 forecast** is published; it does not beat persistence.
- **Risk classes** are a deterministic mapping from the forecast to CPCB tiers and GRAP stages. At 24h the statutory 401 cut-off
  misses crises because Ridge shrinks the peaks; a cost-aware lower threshold is analysed in `reports/classification/`.
- **Diwali effect:** the naive pre/post estimate is dominated by the autumn trend; the interrupted-time-series level shift and the
  placebo test are in `reports/causal/`.

## Frozen vs live-consistent models

Frozen models (`models/*`, hashes in `config/model_hashes.json`) were trained on official AQI. The live pipeline can only compute
AQI from pollutants, which sits above the official series, so the frozen skill does not transfer. The live-consistent retrain
(`models/live/`, hashes in `config/live_model_hashes.json`) uses recomputed AQI as input and target. See
`docs/decisions/0001-frozen-vs-live-consistent-models.md` and `docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`.

## Live pipeline

1. `src/live/` ingests hourly pollutant readings behind one source interface (`config/live.toml`), applies QC and writes `aq.*`.
2. AQI is recomputed from QC'd pollutants (`compute_aqi`, method `rolling_subindex_mean`).
3. `src/live/forecast.py` builds features through the same `compute_feature_frame` as training, serves the products in `src/live/serving.py`
   (checked against `config/live_model_hashes.json`; a mismatch stops the job) and writes forecasts. Weather is not filled in for model
   inputs (`weather_fill = "none"`). Products (`[forecast]` in `config/live.toml`, ADR 0006): AQI 1h is a rule-based window-update forecast,
   AQI 6h and 24h and PM2.5 1h and 6h are the live-consistent models; PM2.5 24h, intervals and P(severe) are off.
4. `python -m src.live.parity_live` compares the served products with the training path (`python -m src.live.parity` does the same for the frozen models).

The workflows are manual (`workflow_dispatch`) until a source is shown to be fresh from a runner; the cron is added in the same
commit that switches the source. Status: `docs/TIER_3/README.md`.

## Conventions

- Heavy work (training, large matrix builds) runs on Colab; local runs are single-threaded.
- Frozen artifacts are never overwritten.
- Docs quote numbers only from generated tables.

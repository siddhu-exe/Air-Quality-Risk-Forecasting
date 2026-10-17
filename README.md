# Delhi Air Quality Risk Forecasting

1h / 6h / 24h AQI forecasts for 7 Delhi monitoring stations, CPCB/GRAP risk classes, and a live pipeline that scores
hash-pinned models on hourly data. Every model is reported next to naive persistence, because the AQI target is a 24-hour
rolling average and persistence is very hard to beat.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

**Dataset:** [Delhi Air Quality Monitoring Dataset (2023-2026) on Kaggle](https://www.kaggle.com/datasets/siddharthdongardive/delhi-air-quality-monitoring-dataset-2023-2026)

## Live status

The live pipeline (ingestion, AQI recompute, forecast job, scoring) and the read-only API (Azure Container Apps) are built and tested. The hourly OpenAQ ingest is scheduled but OpenAQ runs about two days behind real time, so **no live forecast is being issued yet**: the forecast job refuses stale data, and its cron is added once a source has been under 3 hours old for 24 hours straight. WAQI is ingested in shadow mode only. The React frontend runs on sample data until it is rewired to the API.
Dashboard: <https://air-quality-risk-forecasting.vercel.app>.
Details and next steps: [`docs/TIER_3/README.md`](docs/TIER_3/README.md).

## Architecture

```
OpenAQ / data.gov.in  ->  GitHub Actions (ingest, forecast)  ->  Supabase Postgres  ->  FastAPI (Azure Container Apps)  ->  React (Vercel)
                              joblib inference inside the job, no model server
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the [decision records](docs/decisions/README.md).

## Results

Skill = 1 - MAE_model / MAE_persistence on the same rows; CIs are 95% day-block bootstrap intervals. The test window (2025-11-01 .. 2025-12-31) is scored once; every choice is made on validation (2025-09-01 .. 2025-10-31).

### Live basis: models retrained on recomputed AQI (what the live service serves)

The live pipeline can only compute AQI from pollutants, which sits above the official AQI. These are the live-consistent models on the live input view (no NOx/NO/solar, no ITO weather).
**Served products** ([ADR 0006](docs/decisions/0006-live-forecast-products.md)): AQI 1h is a *rule-based (24h-window update)* forecast, not the 1h model below, because the rule beats it; AQI 6h is the model (real skill); AQI 24h is the model, labelled low-skill; PM2.5 1h and 6h are the headline live forecast. No 24h PM2.5, interval or P(severe).
Source: `reports/modeling/live_retrain/live_retrain_metrics.csv`, write-up in [`docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`](docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md).

| Horizon | Split | Inputs | Model | Rows | MAE | Persistence MAE | Skill | Skill 95% CI |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1h | test | live-masked | aqi-1h-lgb-live-v1 | 10,221 | 1.540 | 2.330 | +0.339 | [+0.267, +0.395] |
| 1h | test | unmasked | aqi-1h-lgb-v1 (frozen, reference) | 10,221 | 2.527 | 2.330 | -0.084 | [-0.421, +0.127] |
| 6h | test | live-masked | aqi-6h-lgb-live-v1 | 10,181 | 8.474 | 12.153 | +0.303 | [+0.243, +0.351] |
| 6h | test | unmasked | aqi-6h-lgb-v1 (frozen, reference) | 10,181 | 12.716 | 12.153 | -0.046 | [-0.235, +0.092] |
| 24h | test | live-masked | aqi-24h-hybrid-live-v1 | 10,044 | 33.233 | 36.520 | +0.090 | [+0.051, +0.126] |
| 24h | test | unmasked | aqi-24h-hybrid-v1 (frozen, reference) | 10,044 | 33.602 | 36.520 | +0.080 | [+0.041, +0.114] |

Against a stronger baseline: the live AQI is a 24h mean, so the hours leaving the window are known in advance. Window-update persistence (assume the entering hours equal the current hour) scores +0.553 against persistence at 1h on test, **above the retrained 1h model** (+0.344; model vs window-update -0.467, CI [-0.594, -0.375]). At 6h the window-update baseline is no better than persistence (+0.007) and the model beats it (+0.304, CI [+0.243, +0.357]), so the 6h skill is real. Details: [`docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`](docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md).

Raw PM2.5 (ug/m3, live-consistent), source `reports/modeling/live_pm25/pm25_forecast_metrics.csv`. No 24h PM2.5 forecast is published.

| Horizon | Split | N | Variant | Model MAE | Persistence MAE | MAE skill | Skill 95% CI | RMSE skill |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |
| 1h | test | 9,970 | residual | 24.971 | 31.281 | +0.2017 | [+0.183, +0.219] | +0.1932 |
| 6h | test | 9,862 | level+cal | 64.642 | 101.666 | +0.3642 | [+0.316, +0.407] | +0.3486 |

### Research basis: frozen models on the official AQI

| Horizon | Model | N | MAE | MAE 95% CI | RMSE | RMSE 95% CI | R² | Bias | MAE (AQI≥300) | MAE skill | RMSE skill |
| :--- | :--- | ---: | ---: | :---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 1h | Tuned LightGBM | 10057 | 2.29 | [1.66, 3.16] | 5.08 | [2.88, 7.17] | 0.992 | -0.83 | 2.3 | 0.047 | -0.332 |
| 1h | Naive persistence | 10057 | 2.40 | [2.11, 2.69] | 3.82 | [3.23, 4.42] | 0.995 | -0.14 | 2.3 | 0.000 | 0.000 |
| 6h | Tuned LightGBM | 9998 | 11.84 | [10.33, 13.63] | 15.97 | [13.42, 18.83] | 0.919 | -6.85 | 11.8 | 0.069 | 0.091 |
| 6h | Naive persistence | 9998 | 12.72 | [11.12, 14.41] | 17.58 | [15.08, 19.90] | 0.902 | -0.77 | 11.9 | 0.000 | 0.000 |
| 24h | 50/50 Hybrid (Persistence + Ridge) | 9800 | 34.11 | [29.57, 39.15] | 44.80 | [38.65, 50.84] | 0.365 | -5.12 | 31.9 | 0.110 | 0.117 |
| 24h | Naive persistence | 9800 | 38.34 | [33.09, 44.01] | 50.75 | [43.63, 57.66] | 0.185 | -1.92 | 35.3 | 0.000 | 0.000 |
| 24h | 50/50 Hybrid, +2024 winters (extended train) | 9800 | 34.02 | [29.50, 39.00] | 44.68 | [38.52, 50.91] | 0.368 | -5.90 | 31.5 | 0.113 | 0.120 |

Source: `reports/metrics/headline_metrics.csv` (`python src/evaluation/build_metrics_table.py`). At 1h the tuned model loses to persistence on RMSE and R2; the gains are at 6h and 24h.
The research-basis skill does **not** transfer to the live feed: with recomputed AQI the frozen 1h/6h models are not distinguishable from persistence, which is why the live-consistent models exist.
More results (risk classification, Diwali causal analysis, Tier 2 experiments): [`docs/FINDINGS.md`](docs/FINDINGS.md).

## Quick start

Requirements: Python 3.11+, Node 20+ (frontend only). PostgreSQL 16 is only needed to rebuild the research database from the raw files.

```bash
git clone git@github.com:siddhu-exe/Air-Quality-Risk-Forecasting.git
cd Air-Quality-Risk-Forecasting
python -m venv venv && ./venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env              # fill in only what you need; never commit it
make data                         # download and SHA-256-verify the large datasets (needed by the phase scripts, not by the tests)
make test                         # pytest + frontend tests
make run-api                      # API on :8000 (needs DATABASE_URL_READONLY)
make run-frontend                 # React dev server (sample data)
```

`make help` lists every target. Reproducing the research pipeline step by step is in [`docs/DATA.md`](docs/DATA.md) and `docs/TIER_2/README.md`; heavy training runs in Colab.

## Limitations

- **The target is smoothed.** AQI is a 24-hour rolling average, so judge skill against persistence, not R2.
- **Few test windows.** The headline is one winter (Nov-Dec 2025), very different in level from validation; the rolling-origin backtest adds winter 2024.
- **Live basis.** The live models have never run on live data. The 24h AQI model has low skill, and the 24h interval and P(severe) outputs are not shipped (`docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`).
- **No forecast meteorology.** Models use ground telemetry only; there is no comparison with operational forecasts (IITM AQEWS/SAFAR).
- **Diwali effect is not identifiable** with this data; see `reports/causal/`.
- **Scope.** 7 stations in the National Capital Territory of Delhi.

## Repository layout

```text
src/live/        live ingestion, QC, AQI recompute, forecast job, parity check
src/features/    leakage-safe feature builder, CPCB AQI recompute
src/models/      research and live-consistent training code, splits
src/evaluation/  headline metrics, backtests, live audits
etl/ sql/ db/    research ETL and PostgreSQL schema; Supabase migrations
models/          frozen models (hashes in config/model_hashes.json); models/live/ live-consistent models
backend/ frontend/  read-only FastAPI (`/api/v1`) and React dashboard
docs/            ARCHITECTURE, decisions/, FINDINGS, DATA, TIER_2, TIER_3, history/
reports/         generated metrics, figures and findings
```

## License and attribution

Code: MIT, see [`LICENSE`](LICENSE). Data: environmental telemetry published by the Central Pollution Control Board (CPCB) and Delhi Pollution Control Committee (DPCC), Government of India, under the Open Government Data (OGD) Platform India terms; source portal <https://airquality.cpcb.gov.in/caaqms/>.

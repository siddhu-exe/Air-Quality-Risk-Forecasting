# Delhi Air Quality Risk Forecasting: portfolio project page

Content for the project page on the portfolio site. Every number comes from a report in this repo
(`reports/modeling/live_retrain/`, `reports/live/`, `reports/metrics/headline_metrics.csv`); if this page and those files
disagree, the files win. Figures are regenerated with `make portfolio`.

## Title and pitch

**Delhi Air Quality Risk Forecasting**

Hourly air-quality forecasts for seven Delhi stations, every one scored against "copy the last value", on a live pipeline
that found and fixed the gap between the data the models were trained on and the data they are served.

## The problem

Delhi's AQI is a 24-hour rolling average (lag-1 autocorrelation about 0.998), so "the next value equals the current
value" is very hard to beat, and a forecast that does not beat it is not worth publishing. The goal was a forecast people
could trust, which meant measuring skill against persistence everywhere, with confidence intervals, and being willing to
ship a plain rule where a model loses.

## What I built

1. **Pipeline.** 105 CPCB/DPCC spreadsheets for 7 CAAQMS stations, ETL with QC into PostgreSQL, a leakage-audited feature
   matrix, CPCB-method AQI recomputed from raw telemetry for years the official table does not cover.
2. **Models.** LightGBM for 1h and 6h, a Ridge + persistence hybrid for 24h, CPCB/GRAP risk classes with cost-sensitive
   alert cutoffs chosen on validation only, and a causal (interrupted time series, placebo) study of the Diwali firecracker
   ban that concludes the effect is not identifiable.
3. **Live system.** Scheduled GitHub Actions jobs (ingest, forecast, score, shadow ingest) write to Supabase Postgres; a
   read-only FastAPI on Azure Container Apps serves a React dashboard on Vercel. Models are hash-pinned and run inside the
   job, with no model server.

**Stack:** Python, PostgreSQL / Supabase, LightGBM, scikit-learn, statsmodels, FastAPI, Azure Container Apps, GitHub
Actions, React + TypeScript + Vite, Tailwind, TanStack Query, Vercel, pytest, Playwright.

## Three key findings

### 1. Train/serve skew: retrain on the data the service actually sees

The live feed can only compute AQI from pollutants, and that series sits about 5.5 points above the official AQI the first
models were trained on. On the live basis the frozen models lose their skill; retrained on the recomputed AQI (same
architecture, same features) they recover it. Test winter, skill against persistence:

| Horizon | Frozen model | Live-consistent retrain |
| :--- | :---: | :---: |
| 1h | -0.084 [-0.421, +0.127] | +0.339 [+0.267, +0.395] |
| 6h | -0.046 [-0.235, +0.092] | +0.303 [+0.243, +0.351] |
| 24h | +0.080 [+0.041, +0.114] | +0.090 [+0.051, +0.126] |

An isotonic recalibration of the frozen models was tried first and rejected on validation. *Figure: 60_train_serve_skew.*

### 2. A rule beats ML at 1h; ML wins at 6h

Recomputed AQI is a trailing 24h mean, so most of what looks like 1h forecast skill is arithmetic: the hours leaving the
window are already known. A parameter-free window-update rule has test skill +0.553 at 1h; the tuned model has +0.344 and
loses to the rule (-0.467, CI [-0.594, -0.375]). At 6h the rule is indistinguishable from persistence (+0.007) and the
model wins (+0.309 against persistence, +0.304 against the rule). So the service serves the rule at 1h and the model at 6h.
*Figure: 61_baselines_by_horizon.*

### 3. Dead live sources: probe, shadow mode, gate

The primary source (OpenAQ) runs days behind real time. Instead of guessing, I probed from a GitHub runner (US egress,
2026-10-11): `api.data.gov.in` refused the connection, and OpenAQ's newest value was 91.8 h old, so the lag was the source's,
not a network effect. I verified OpenAQ against the raw CSVs (units, hour convention, sensor choice), ran WAQI in shadow mode
in a separate table that no forecast or API code can read, and fixed the fallback rule before the data arrives: PM only, ITO
excluded, offset chosen on the first half of the overlap and scored on the second, per-station pass. A weekly job applies
it and posts the result to a GitHub issue. Until a source is fresh the dashboard says so and shows the last issued forecast
labelled as past, rather than inventing a forecast. *Figures: 10_architecture, dashboard screenshots.*

## Results (test winter, Nov 1 to Dec 31, 2025; scored once)

Live basis (what the service runs), MAE in AQI points, skill = 1 - MAE_model / MAE_persistence, 95% day-block bootstrap:

| Product | Model MAE | Persistence MAE | Skill vs persistence |
| :--- | ---: | ---: | :---: |
| AQI 1h, window-update rule | 1.041 | 2.330 | +0.553 [+0.510, +0.591] |
| AQI 1h, LightGBM (not served) | 1.540 | 2.330 | +0.339 [+0.267, +0.395] |
| AQI 6h, LightGBM | 8.474 | 12.153 | +0.303 [+0.243, +0.351] |
| AQI 24h, hybrid (experimental) | 33.233 | 36.520 | +0.090 [+0.051, +0.126] |
| PM2.5 1h | 24.971 | 31.281 | +0.202 [+0.183, +0.219] |
| PM2.5 6h | 64.642 | 101.666 | +0.364 [+0.316, +0.407] |
| PM2.5 24h | withheld | 75.416 | no skill (-0.102 [-0.238, +0.010]) |

Replay of the production code on stored readings, 2026-09-01 to 2026-10-07 (a sanity check, not a live result):

| Product | MAE | Persistence MAE | Skill vs persistence |
| :--- | ---: | ---: | :---: |
| AQI 1h | 0.90 | 1.84 | +0.514 [+0.460, +0.564] |
| AQI 6h | 6.89 | 8.67 | +0.206 [+0.124, +0.285] |
| AQI 24h | 26.39 | 26.03 | -0.014 [-0.104, +0.058] |
| PM2.5 1h | 8.90 | 9.72 | +0.084 [+0.053, +0.110] |
| PM2.5 6h | 16.71 | 21.10 | +0.208 [+0.140, +0.270] |

Original models on the official AQI (`reports/metrics/headline_metrics.csv`): 1h MAE 2.29 vs 2.40 (+0.047), 6h 11.84 vs
12.72 (+0.069), 24h 34.11 vs 38.34 (+0.110).

## Limitations

- **No live forecast is being issued today.** OpenAQ is behind real time, so the forecast job skips stale stations and the
  dashboard shows a notice and the last issued forecast as history. The skill numbers above are test-window and replay
  numbers, not live-scored ones; the live scoreboard fills in once forecasts mature.
- AQI 1h skill against plain persistence is mostly the window identity, not forecasting; the 24h AQI model has low skill
  and is labelled experimental; 24h PM2.5 is withheld.
- The replay window is Sep to Oct, a calmer season than the winter test; the 24h replay skill is not distinguishable from
  zero.
- Live AQI is recomputed from pollutants, not the official CPCB value; no NOx, NO or solar and no ITO weather on the live
  feed.
- No upstream source is both reachable and fresh (data.gov.in refuses connections; OpenAQ lags); the WAQI gate currently
  fails for lack of overlap with OpenAQ.
- The Diwali causal question cannot be answered with this data (the ban applied in every year studied).

## Links

- GitHub: https://github.com/siddhu-exe/Air-Quality-Risk-Forecasting
- Live dashboard: https://air-quality-risk-forecasting.vercel.app
- API docs: https://ca-delhi-air-api.lemoncliff-0c3c829f.centralindia.azurecontainerapps.io/api/docs
  (scale-to-zero, so the first request can take several seconds)
- Dataset: https://www.kaggle.com/datasets/siddharthdongardive/delhi-air-quality-monitoring-dataset-2023-2026
- Case study: `docs/CASE_STUDY.md`

## Which figure goes where

All files are in `portfolio/images/` (PNG; drawn figures are 1600 px wide; screenshots are 1440 px desktop and 390 px mobile).

| Place on the page | File |
| :--- | :--- |
| Hero | `dashboard_overview_desktop.png` |
| What I built | `10_architecture.png` |
| Finding 1 | `60_train_serve_skew.png` |
| Finding 2 | `61_baselines_by_horizon.png` |
| Finding 3 | `dashboard_model_health_desktop.png` |
| Results | `62_replay_skill.png`, `30_skill_vs_persistence.png` |
| Pipeline and models gallery | `21_splits_timeline.png`, `31_extrapolation_fix.png`, `32_episode_forecast.png` |
| Alerting and causal gallery | `50_alert_tradeoff.png`, `51_diwali_identification.png` |
| Mobile strip | `dashboard_overview_mobile.png`, `dashboard_stations_mobile.png`, `dashboard_model_health_mobile.png` |
| Stations page | `dashboard_stations_desktop.png` |

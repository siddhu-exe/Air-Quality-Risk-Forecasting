# Tier 3: take the forecasts live (resume guide)

State on 2026-10-15 (first written 2026-10-11). The full plan, decisions and evidence are in [`PLAN.md`](PLAN.md); this page is what you need to pick the work up again.

## What exists (all on `main`)

| Piece | Where | Notes |
| :--- | :--- | :--- |
| Database | Supabase project `delhi-air-quality-live` (ap-south-1), schema `aq`; `db/migrations/001-007` | RLS on every table; `job_writer` (no delete) and `api_readonly` roles; connect only through `DATABASE_URL` / `DATABASE_URL_READONLY` |
| Backfill | `python -m src.live.backfill` | local CSVs 2026-01-01..08-31 (`local_csv_2026`) + OpenAQ 09-01..10-07 (`openaq`); loaded |
| Sources | `src/live/sources/` (`openaq`, `data_gov_in`), `src/live/openaq.py`, `qc.py` | one interface, chosen by `config/live.toml` / `LIVE_SOURCE`. OpenAQ verified; data.gov.in **unverified** (refused unless `allow_unverified`) |
| Ingest | `python -m src.live.ingest [--dry-run]`, `.github/workflows/ingest.yml` | manual workflow; fails when no station is fresh |
| Forecast | `python -m src.live.forecast [--dry-run] [--issue-time "YYYY-MM-DD HH:MM"]`, `.github/workflows/forecast.yml` | frozen 1h/6h/24h models, hash-checked; skip reasons in `job_runs.details`; manual, dry run by default |
| Audit and parity | `src/evaluation/feature_availability_audit.py`, `src/live/parity.py`; reports in `reports/modeling/live_audit/` and `docs/TIER_3/parity_report.md` | D1 audit (validation only) and parity with the stored backtest predictions |
| WAQI | `src/live/epa_aqi.py`, `src/live/waqi_station_check.py`, `src/evaluation/waqi_roundtrip_audit.py`; `docs/TIER_3/waqi_stations.md` | candidate third source (`api.waqi.info`, per-pollutant US-EPA AQI, no NOx, no history). All 7 stations map and are fresh (ITO only via a different monitor 1.9 km away); **gas readings look implausible** (2nd-4th percentile of last October), so only PM is trustworthy until verified. No ingest code yet |
| Live-consistent retrain | `src/features/build_live_matrix.py`, `src/models/live_retrain.py`, `scripts/generate_live_retrain_notebook.py` -> `notebooks/live_retrain_colab.ipynb` + `tier3_live_retrain_bundle.zip` | **waiting for the Colab run**; new models go to `models/live/` (`aqi-*-live-v1`); `src/evaluation/calibration_side_check.py` is the validation-only alternative |
| Probe | `.github/workflows/probe-sources.yml` | **never run** |

Config in `config/`: `live.toml` (source, lookback, stale limit, `weather_display`, `weather_fill`), `model_hashes.json`, `forecast_gate.json`.
Dev machine: set `FORCE_IPV4=1` (IPv6/NAT64 hangs). Local venv has no LightGBM: the 1h/6h tests and parity skip unless it is installed
(`requirements-forecast.txt` pins what CI should use). Tests: `./venv/bin/python -m pytest` (199 pass, 2 skip without the git-ignored training files or LightGBM).

## Decisions in force

- **D1 option A is superseded (2026-10-15).** Live AQI is recomputed and sits ~5.5 points above the official AQI the frozen models were trained on; on the live basis the frozen models' validation skill vs persistence is about +0.04 (1h), +0.07 (6h), +0.04 (24h), CIs including zero (`reports/modeling/live_audit/waqi_roundtrip_audit.md`). Decision: re-fit the same architectures on recomputed AQI (input and target), test scored once; the Colab run produces them. Do not serve the frozen models as the live headline until that is settled. Open-Meteo weather is stored for display but **not** fed to the models (`weather_fill = "none"`): filling hurt the 1h/6h models on validation.
- OpenAQ is the primary source once fresh; data.gov.in only becomes a fallback after its fields, units and hour convention are verified.
- Forecasts are immutable per (issue hour, station, horizon, target). No 24h PM2.5. 1h AQI is shown next to persistence (it is about equal to it).
- D2 (export-only re-fit of the PM2.5 / quantile / P(severe) models) is prepared in the same Colab notebook (PM2.5 on live-masked inputs, so it doubles as the live-consistent PM2.5 audit); until it is run, no intervals, no P(severe), no PM2.5. If PM2.5 1h/6h skill holds it becomes the headline live forecast.

## Blocked on you

1. **Run the probe** (Actions > `probe-sources` > Run workflow; needs `DATA_GOV_IN_API_KEY` and `OPENAQ_API_KEY` secrets). It answers: can a runner reach data.gov.in, what are its real fields, units and hour convention, and is OpenAQ fresh from a runner. Send me the log.
2. **A fresh source.** WAQI is live today (see above) but unverified for gases and has no history, so it cannot backfill the 336 h feature window by itself. OpenAQ's newest value is 2026-10-07 (0 of 7 stations fresh on 2026-10-11); data.gov.in refuses connections from the dev laptop (`curl` returns `000`). If the probe shows neither works, the written option is an Azure Container Apps Job in Central India: [`OPTION_azure_ingest_job_india.md`](OPTION_azure_ingest_job_india.md) (needs your decision; nothing is built).
3. Secrets: `DATABASE_URL` (added), `DATABASE_URL_READONLY` (needed for the forecast dry run).

## Next steps once a source is fresh

1. Run `ingest.yml` by hand, check `job_runs`, then add the `10 * * * *` cron in the same commit that selects the source. Same for `forecast.yml` (`25 * * * *`).
2. Stage 4: `score.py` + `score.yml` (score matured forecasts into `forecast_scores` / `skill_rolling`; open an issue when 24h skill < 0 for 7 days or 3 jobs fail in a row).
3. Stage 5: FastAPI `/api/v1` reading the DB, Dockerfile, deploy workflow (you create the Azure resources); Stage 6: merge the rebuilt frontend (branch `frontend/rebuild`, rebased on main, deliberately unmerged until the Stage 5 API fixes its endpoints), point it at the API; Stage 7: `models/registry.json`, `ci.yml`, final README, `TIER_3_LOG.md`.
4. Run the Colab bundle (steps in the 2026-10-15 hand-off: upload `tier3_live_retrain_bundle.zip` to Drive `aq_tier3_live`, open `notebooks/live_retrain_colab.ipynb`, send back `tier3_live_retrain_results.zip`), then compare it with `calibration_side_check` on validation and write `docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`.

## Known limits to carry

- Parity: 24h reproduces the stored predictions to 6e-12; 1h/6h reproduce them exactly only when the rolling windows start where training's did; with the job's short window a few rows differ (max 0.09 / 0.57 AQI) from last-digit rolling noise.
- The 24h model's multi-day lags are row-based, as in training. A station with AQI gaps gets slightly different lags than an hour-based reading would, exactly as in the backtest.
- Live AQI is recomputed from live pollutants (`recomputed_live`), not the official CPCB value; NH3 is missing from OpenAQ (immaterial: 0 values changed in Sep-Oct 2025). Dwarka's 2026 hour alignment is unverified.
- Audit skill numbers are validation-window numbers (a calmer season than the winter test window); the test headline is in `reports/metrics/headline_metrics.csv`.

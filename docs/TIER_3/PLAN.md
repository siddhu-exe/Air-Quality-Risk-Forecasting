# Tier 3 plan — take the forecasts live

Status (2026-10-11): **Stages 1-3 are built, tested and on `main`; Stages 4-7 are not started.** Nothing is scheduled yet:
`ingest.yml` and `forecast.yml` are manual (`workflow_dispatch`) because no live source is known to be fresh from a GitHub runner.
Start from `docs/TIER_3/README.md` (resume guide: what exists, how to run it, what is blocked, what to do next). The sections below are
the original plan, kept in line with what was built; the Progress log records the evidence.
Everything marked **TODO(verify)** could not be confirmed from a primary source in this session
and must be checked before the stage that depends on it. No number from a model is typed in this
document; metric values live in `reports/metrics/headline_metrics.csv`.


> **Correction, 2026-10-15 (D1 numbers).** The D1 audit scored every scenario against the *official* AQI, but the live pipeline
> recomputes AQI from pollutants (`compute_aqi`), and the recomputed series sits on average 5.5 AQI points above the official one
> (MAE 8.0 on validation rows; `reports/modeling/live_audit/waqi_roundtrip_aqi_error.csv`). The frozen models were trained on the
> official series. So the D1 headline skills (1h +0.342, 6h +0.200 vs persistence) are **not what live delivers**. With recomputed AQI as
> input and label (persistence on the same series), the frozen models score, on validation, with no input degradation at all:
> 1h +0.044 [-0.053, +0.135], 6h +0.066 [-0.055, +0.171], 24h +0.038 [-0.011, +0.079] (95% day-block CIs, all rows;
> `waqi_roundtrip_audit.csv`, scenario `control_recomputed`, basis `own`). All three intervals include zero. Feeding recomputed AQI
> to the frozen models scored against official labels is worse still (1h -1.94). Decision 2026-10-15: re-fit the same architectures on
> recomputed AQI as input and target (`src/models/live_retrain.py`, new versions under `models/live/`), with a calibration of
> recomputed to official as a side check (`src/evaluation/calibration_side_check.py`); results go to
> `docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md` once the Colab run is back. Until then the live forecast uses no claim of skill at 1h/6h.

---

## 0. Read this first: four blockers found in the read-through

(Historical: written before the build. All four were resolved or carried as decided; section 9 and the Progress log say how.)

### B1. The live source cannot supply every input the frozen models were trained on

| Model | Inputs it needs (from the artifacts, not from memory) | Live CPCB feed provides |
| :--- | :--- | :--- |
| 1h / 6h LightGBM (`models/lgb_model_{1h,6h}_v1.joblib`) | 131 features: AQI + pollutant lags (PM2.5, PM10, NO2, **NOx**, SO2, CO, O3), rolling stats, **calendar** (hour, month, day-of-year, sin/cos…), **station-measured temp / humidity / wind speed / solar radiation** (24 features), network/neighbour lags, 7 station one-hots | PM2.5, PM10, NO2, NH3, SO2, CO, O3 only (TODO(verify) with a real key). **No NOx, no on-site meteorology.** |
| 24h hybrid (`models/24h/final/`, 49 features) | AQI lags/rolls/deltas, PM2.5, PM10, NO2, **NOx**, SO2, CO lags, network means. No meteorology, no calendar. | Same gap: the four `nox_lag_*` features. |

The feature list for 1h/6h was read from the model text inside the joblib (no LightGBM needed);
the 24h list from `feature_names_final.joblib`.

If NOx / weather arrive as NaN the 24h imputer fills them with the training median and LightGBM
routes them down its "missing" branch. The job would run and produce numbers that are **not** what
the backtest measured. That is the silent failure the plan forbids, so the forecast job will
refuse to run a model when any required feature group is 100% missing, unless one of the options
below is chosen.

Options (decision D1 in section 9):

- **A. Substitute and measure.** Fill temp/humidity/wind/solar from Open-Meteo (reanalysis /
  analysis values, not the on-site sensor) and leave NOx NaN. Before enabling, run a
  *feature-availability audit* on **validation only**: re-score the frozen models on the
  validation window with NOx masked and weather swapped for ERA5 (we already have
  `data/processed/exogenous_weather.parquet`). The 24h Ridge can be audited locally; the LightGBM
  models need Colab (no LightGBM locally, weak laptop). If skill vs persistence survives, ship with
  the shift disclosed. Not retraining.
- **B. Retrain "live-feature" models** restricted to what the feed supplies. This is the more
  defensible serving design, but it contradicts "do not retrain anything in this tier", so it needs
  your explicit go-ahead and would be a Colab job producing new `model_version`s evaluated by the
  same protocol (validation selection, test scored once).
- **C. Ship NaN and hope.** Rejected.

My recommendation: **A as a gated audit first, B only if the audit shows the frozen models lose
their edge.** The audit costs one Colab run and decides it with evidence.

### B2. The primary live source has no history, so the 14-day backfill is not possible from it

The data.gov.in feed returns the latest hourly reading per station-pollutant; I found no
history parameter. The feature builder needs, per station, 168 h of lags plus a 24 h AQI window
(8+ days of hourly data) before the first valid forecast. Options:

- Backfill from **OpenAQ v3** (`/v3/sensors/{id}/hours`, precomputed hourly), if it carries these
  stations (TODO(verify): which parameters each Delhi sensor exposes; I could not confirm NOx or
  meteorology there either).
- Or accept a **cold start**: ingest for ~9 days, forecasts skipped (with a recorded reason) until a
  station has enough data. Zero extra code, honest, but the demo is empty for a week.

Related risk: with a snapshot-only source, an hour the job misses is lost for ever. Ingestion
must be idempotent so extra runs are harmless; I propose a second, cheap catch-up run (minute 40)
in addition to your minute 10. Gaps beyond what the 16-of-24 AQI rule tolerates make a station
"skipped", never imputed.

### B3. The Tier 2 PM2.5 and quantile / conformal / P(severe) models are not saved anywhere

`train_pm25_forecast.py` and `train_quantile_forecast.py` fit scikit-learn
`HistGradientBoosting*` models inside `main()` and write only reports; there is no `joblib.dump`
in any Tier 2 script. So "load the PM2.5 and quantile models" has nothing to load.

Also, by what Tier 2 actually produced:

- Quantile (q10/q50/q90), the conformal pad and P(AQI ≥ 401) exist for **24h AQI only**. The
  `forecasts` columns `q10/q50/q90/p_severe` will be NULL for 1h/6h and for PM2.5.
- PM2.5 models are served for **1h and 6h only**. 24h PM2.5 lost to persistence on the test winter;
  it is not trained into the live path and never shown.

Fix (decision D2): an **export-only Colab run** that re-fits the already-accepted configurations
(variants and iteration counts from `reports/modeling/pm25/variant_selection.csv` and
`probabilistic_metrics.json`, no new selection) and saves joblib files + the conformal pad. That is
a re-fit, not a new experiment, but it does train, so I am asking first. Until it exists, the
forecast job serves the frozen AQI models only, and PM2.5 / intervals / P(severe) stay off.

### B4. Smaller issues to carry

- **Train/serve skew in the AQI input.** The frozen 1h/6h/24h models were trained on *official*
  AQI for 2025. Live AQI is *recomputed* from live pollutants (`aqi_source = recomputed_live`); the
  recompute was validated against official 2025 with a positive bias at high AQI (see
  `reports/features/aqi_recompute_validation.md`). Live scoring compares against the same recomputed
  series, so skill-vs-persistence is internally consistent, but absolute AQI will differ from what
  CPCB publishes. Stated everywhere in the UI.
- **Timestamp convention.** I have not confirmed whether the raw CSV `Timestamp` marks the start
  or the end of the averaging hour, nor how the feed's `last_update` relates to it. Wrong by one
  hour would shift every lag. Stage 2 includes an alignment check against a historical overlap
  (OpenAQ, December 2025, vs the raw CSVs) if OpenAQ is usable; otherwise it stays a flagged risk.
- **Parity may expose a pre-existing difference.** `load_raw_data_offline` reads raw CSVs with no
  QC, while training for 1h/6h used the Postgres path (ETL QC applied). If the Stage 3 parity test
  fails at 1e-6 for that reason I will report it, not loosen the tolerance.
- **Tests run where LightGBM exists.** The local venv has no LightGBM. The 1h/6h parity test uses
  `pytest.importorskip("lightgbm")` and runs in CI; the 24h parity test runs locally.
- **Weather is not a forecast.** Open-Meteo values are observed/analysis only; the models were never
  fed forecast weather. Stated as a caveat.

---

### Progress log

- **2026-10-11, Stage 1 complete.** Schema `aq` with migrations 001-007 applied and verified (RLS on all tables, role
  tests, advisors clean). Both role logins verified from the code path (`job_writer` cannot delete; `api_readonly` is
  read-only at session level). 7 stations loaded with OpenAQ coordinates.
- **Backfill loaded** (`python -m src.live.backfill`): 35,276 hourly readings and 34,563 AQI rows. Local CSVs for
  2026-01-01..08-31 (six stations; none for Dwarka-Sector 8) tagged `local_csv_2026`, OpenAQ for 2026-09-01..2026-10-07
  tagged `openaq`. Verified through the read-only login: a stored value equals the CSV value, timezone round-trips,
  the Dwarka rows carry `{"_alignment": "unverified_2026"}`. OpenAQ-period gaps are larger than the CSV period
  (PM2.5 missing 5-23% vs 2-5%): a strict four-slots-per-hour rule plus real outages. No NH3 or solar from OpenAQ, so
  AQI from September has no NH3 sub-index.
- **Feature path:** `compute_feature_frame` / `add_cross_station_features` split out of `assemble_feature_matrix`;
  output bit-for-bit identical to the original on synthetic data (two seeds). `load_caaqms_offline` split out of
  `load_raw_data_offline`.
- **D1 audit:** built (`src/evaluation/feature_availability_audit.py`, `notebooks/d1_feature_audit_colab.ipynb`,
  `tier3_d1_audit_bundle.zip`). The 24h hybrid part ran locally on validation: see
  `reports/modeling/live_audit/feature_availability_audit.md`. The 1h/6h LightGBM part is waiting for a Colab run.
- **Probe workflow** committed locally on branch `tier3/probe-sources`; not pushed. data.gov.in result from the user's
  Indian network not yet received.
- **D1 baseline reconciled.** The audit baseline now reproduces Tier 2's stored frozen-model validation predictions exactly
  (9,590 rows, MAE 29.024 vs persistence 30.708, max per-row difference 0.000000); the audit refuses to run otherwise. The earlier
  28.454 / 29.935 came from dropping the 168 rows of 2025-10-31 (labels on 2025-11-01) by cutting the feature index at the window
  end; that day is the hardest in the window (model MAE 60.95, persistence 74.04). Imputer/scaler/Ridge are the frozen files (no
  refit), no embargo applies (nothing is trained), and rebuilt features give identical predictions. Tier 2's 28.80 is the
  *extended* model, a different model. The table is in `reports/modeling/live_audit/feature_availability_audit.md`.
- **NH3 check (2025, 7 stations):** NH3 is never the maximum sub-index (its sub-index peaks at 87 against a median top
  sub-index of 182). Removing NH3 changes 0.13% of hourly AQI values over the year (mean 0.008, max 36.9) and 0 values in
  Sep-Oct. The missing NH3 in the OpenAQ-period AQI is immaterial.
- **Stage 2 code written, mocked tests only** (no real data.gov.in call; nothing pushed except the probe branch):
  `src/live/{config,store,weather,ingest}.py`, `src/live/sources/{base,openaq_source,data_gov_in}.py`, `config/live.toml`,
  `.github/workflows/ingest.yml`, `requirements-live.txt`. Both sources implement one interface; the source is a config value
  (`config/live.toml`, overridden by `LIVE_SOURCE` env / repo variable / dispatch input). data.gov.in is marked **unverified** and
  refused unless `allow_unverified` is set. The ingest fails (non-zero exit, `job_runs.status = failed`) when no station is fresh,
  e.g. while OpenAQ's feed is stale; a source-wide unit/scale change is caught by a batch-level plausibility check (a defect in
  the first version, found by its own test: the per-frame guard needs 20 values per column and an hourly run has 6).
- The planned schedule is the `:10` cron only (the `:40` catch-up proposed earlier was not adopted). OpenAQ is re-fetched over
  a 6-hour lookback each run, so a missed run is repaired; the data.gov.in snapshot feed cannot repair a missed hour.
- **`ingest.yml` is `workflow_dispatch` only for now (decision 2026-10-11).** OpenAQ is known to be stale, so an hourly run would
  only be a red run. The cron is added in the same commit that switches to a source the probe has shown to be fresh from a runner.
- **Audit reports two row sets** per horizon and scenario: `all` (9,590 rows at 24h, guarded against Tier 2's stored predictions)
  and `strict` (9,422 rows, label also inside the validation window). 24h baseline: all 29.024 vs 30.708 (skill +0.055), strict
  28.454 vs 29.935 (+0.049); data.gov.in scenarios cost +0.064 / +0.056 MAE. The 1h/6h rows still need the Colab run (the
  `d1_audit_results.zip` received on 2026-10-11 held the Tier 2 reports, not the live-audit folder).
- **Azure ingest-job option** written up in `OPTION_azure_ingest_job_india.md`; applies only if runners are blocked and
  OpenAQ stays stale.

- **Decisions 2026-10-11 (after the audit).** D1 option A accepted: no retrain. `weather_fill = "none"` for forecast inputs (filling hurt
  the 1h/6h models on validation); Open-Meteo values are still stored in `live_readings` for display (`weather_display = "open-meteo"`,
  tagged `weather_source`/`qc_flags`), and the forecast job masks every `filled:*` cell before the models see it. OpenAQ is the
  primary source once fresh; data.gov.in is a fallback only after its fields, units and hour convention are verified. `curl
  https://api.data.gov.in/` from the development laptop (Indian network): no HTTP status; the default route timed out after 20 s
  and IPv4 was refused at connect (`000`, exit 28 / 7). The probe workflow is on `main`; the GitHub-runner result is pending.
- **Stage 3 (forecast job) built, not yet scheduled.** `src/live/{models,forecast,forecast_store,parity,calibrate_gate}.py`,
  `config/{model_hashes,forecast_gate}.json`, `forecast.yml` (manual, dry run by default), `requirements-forecast.txt`.
  *Parity with the stored backtest predictions* (`docs/TIER_3/parity_report.md`): 24h hybrid reproduces them to 6e-12 (validation and
  test, ~300 rows each). 1h/6h reproduce them exactly (0.0) when the rolling windows start where training's did; with the job's
  short history window 35 of 313 (1h, max 0.09 AQI) and 6 of 319 (6h, max 0.57 AQI) rows differ because pandas' rolling mean/std
  differ in their last digits and flip a LightGBM split sitting on a threshold. Tolerance not loosened; limit documented.
  *Finding:* the 24h model's multi-day features are ROW-based (n rows back, on rows that have an AQI), not hour-based; an hour-based
  version missed the stored predictions by up to 53 AQI, so the job keeps the training behaviour.
  *Gate:* skip a station if the share of missing core features exceeds 0.22 (99th percentile over 9,853 validation rows), or a
  required group is absent for the whole window, or it has < 169 AQI rows, is stale (> 3 h) or has no AQI at the issue hour.
  *Run against the backfilled DB* (read-only replay of 2026-10-07 12:00): 5 of 7 stations forecast, Jahangirpuri skipped (stale, 9 h), Punjabi
  Bagh skipped (22.2% core features missing against a 22.0% limit). Write path proven inside a rolled-back transaction as `job_writer`
  (registry upsert, 15 forecast rows, re-insert of the same hour writes nothing). Forecasts are immutable once written.

## 1. Components and data flow

```
 data.gov.in / OpenAQ ──┐
 Open-Meteo ────────────┤  GitHub Actions (planned cron :10; manual until a source is fresh)
                        ▼
              src/live/ingest.py  ──► Supabase Postgres (pooler, DATABASE_URL)
                        │               stations, live_readings, live_aqi,
                        ▼               forecasts, forecast_scores, job_runs, model_registry
              src/live/forecast.py  (own job, run after the ingest; joblib models from git, hash-checked)
                        │
              nightly: src/live/score.py ──► forecast_scores ──► GitHub issue on degradation
                                                  ▲
 React app (Vercel) ──► FastAPI (Azure Container Apps, scale-to-zero, read-only DB role)
```

- **No model server.** Inference runs inside the Actions job; the API only reads rows.
- **Frozen artifacts.** `models/**` and `reports/modeling/24h/final/final_predictions.parquet` are
  never written. New models (decision D1/D2) go to `models/live/` with their own registry rows.
- **One feature path.** `engineer_station_features` and the cross-station block of
  `assemble_feature_matrix` are reused. `assemble_feature_matrix` also wrote a parquet and a manifest, so it was
  split into a pure `compute_feature_frame(...)` plus the I/O wrapper (done, behaviour-preserving, regression-tested). The 24h-only features come from `construct_causal_long_horizon_features` in
  `phase_6c_refinement.py`, imported, not copied. The live path never re-implements a feature.

## 2. Live sources (what I verified, what I did not)

| Item | data.gov.in "Real time Air Quality Index from various locations" | OpenAQ v3 | Open-Meteo |
| :--- | :--- | :--- | :--- |
| Role | first choice, current hour | backfill + fallback | weather (decision D1) |
| Endpoint | `https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` (id from third-party guides; TODO(verify)) | `https://api.openaq.org/v3/...`, key in `X-API-Key` header (TODO(verify) header name) | `https://api.open-meteo.com/v1/forecast` with `past_days` (0–92, documented) for recent hours; the archive API (existing code) lags several days (TODO(verify) exact delay) |
| Status | **Conflict:** guides show it working; the official data.gov.in resource page was reported (search snippet) as saying no API exists for the resource, and the page itself returned 403/503 to me | documented | documented |
| Fields | `country, state, city, station, last_update, pollutant_id, pollutant_min, pollutant_max, pollutant_avg` (R/py client docs); latitude/longitude TODO(verify) | location, sensor, parameter, units, datetime | hourly temperature_2m, relative_humidity_2m, wind_speed_10m, shortwave_radiation, … |
| Pollutants | PM2.5, PM10, NO2, NH3, SO2, CO, OZONE (TODO(verify)) | per-sensor, TODO(verify) NOx / met coverage | n/a |
| Update frequency | hourly (TODO(verify)); timezone of `last_update` (TODO(verify)) | ~hourly, provider-dependent | hourly |
| Limits | sample key is capped at 10 records; personal key limits TODO(verify); possible blocking of non-Indian IPs (GitHub runners are in US datacentres) TODO(verify) | free: 60 req/min, 2,000 req/h per key (official docs); 429 on breach | free: 600/min, 5,000/h, 10,000/day, non-commercial, CC BY 4.0 attribution (official pricing page) |
| Units | µg/m³, CO in mg/m³ (must match `POLLUTANT_COLUMNS`) TODO(verify) | per sensor, convert | °C, %, m/s (check km/h default), W/m² |

First action of Stage 2: one authenticated call to each of data.gov.in and OpenAQ from a GitHub
runner (not the laptop) to settle every TODO above, then rewrite this table with observed values.
I will not use anyone's shared sample key.

### 2a. Observed source facts (2026-10-11; supersede the TODOs above where they overlap)

**data.gov.in.** `www.data.gov.in` answers, but `api.data.gov.in` (164.100.61.198:443) returns `Connection
refused` over plain IPv4 from the development machine. Not yet tested from a GitHub runner or from the user's own
network, so nothing is known about fields, units, cadence or limits. Per decision D4/source rule: if a runner is also
refused, OpenAQ becomes the primary source.

**OpenAQ v3** (key in `X-API-Key`; 60 requests/minute confirmed by the response headers). Full evidence:
`docs/TIER_3/openaq_overlap_check.md`, reproducible with `python -m src.live.openaq_overlap_check`.
- Use the CPCB-provider locations: Anand Vihar 235, Bawana 8472, Dwarka-Sector 8 6931, ITO 5613,
  Jahangirpuri 8235, Punjabi Bagh 50, R K Puram 17. Same-named `caaqm`-provider locations ended in 2018-2022.
- Use the highest sensor id per parameter; the old ids (< 1,000,000) stopped in 2018.
- **B1 is largely answered:** these stations carry NOx and on-site temperature, humidity, wind speed. Missing:
  solar radiation everywhere; all three weather variables at ITO.
- **Unit labels are wrong; numbers match our columns.** NO2, SO2, CO tagged ppb equal our ug/m3 / mg/m3. NOx tagged
  ppb is ppm (multiply by 1000). Convert from the measured relationship, never from the label.
- **Timestamp convention (B4, resolved for this source):** OpenAQ stores 15-minute slots; the CSV value at hour T is the
  mean of the four slots starting at T (temperature and humidity: starting 15 minutes earlier). With that rule, six
  stations agree with the CSV to 0.3-3.3% mean absolute error, correlations 0.965-0.997 (all parameters pass the
  criteria in the report). Use `/sensors/{id}/measurements` (15-minute), not `/hours`, which averages differently.
  Dwarka-Sector 8 has no 2026 CSV and could only be checked on Dec 2025, where labels sit one 15-minute step earlier;
  its 2026 behaviour is unverified.
- Station coordinates from OpenAQ metadata replace the approximate ones (`aq.stations.coords_approximate = false`).
- **Freshness problem:** the newest value at every station was 2026-10-07 14:30 UTC, 88 hours old at check time
  (Jahangirpuri 105 h). A backfill of the last 10 days therefore cannot reach "now" until that feed catches up, and
  OpenAQ is not a live source while this lasts. Cause unknown (CPCB feed or OpenAQ ingestion); re-check before relying on it.
- Local `Og Data/` also contains **2026-01-01 .. 2026-08-31** hourly CSVs for six stations (none for Dwarka-Sector 8),
  never used by the training loaders. They can fill most of the history before September if wanted.
- Development-machine quirk: Python `requests` hangs on this machine's NAT64 IPv6 route; set `FORCE_IPV4=1`. Not an
  issue for GitHub runners.

## 3. Database schema (Stage 1 migrations in `db/migrations/`)

All timestamps `TIMESTAMPTZ`, interpreted as Asia/Kolkata at the edges, as in the existing schema.
Station ids stay 3–9 (as `STATION_IDS` in `compute_cpcb_aqi.py`) so the unchanged feature code works.

| Table | Key columns |
| :--- | :--- |
| `stations` | `station_id` PK, `station_name` UNIQUE, `feed_name` (name in the live feed), `latitude`, `longitude`, `coords_approximate BOOLEAN` (true until real coordinates come from the feed; today only the approximate ones in `exogenous_drivers.py` exist) |
| `live_readings` | `station_id`, `ts`, `pm25, pm10, no2, nox, nh3, so2, co, o3`, `temperature, humidity, wind_speed, solar_radiation`, `weather_source`, `qc_flags JSONB`, `source`, `ingested_at`; **UNIQUE(station_id, ts)** |
| `live_aqi` | `station_id`, `ts`, `aqi`, `aqi_source` CHECK = `'recomputed_live'`, `n_pollutants`, `n_valid_hours`; UNIQUE(station_id, ts) |
| `forecasts` | `issue_time, target_time, station_id, horizon, target ('aqi'\|'pm25'), model_version, y_hat, q10, q50, q90, p_severe, y_persistence, created_at`; **UNIQUE(issue_time, station_id, horizon, target)**; CHECK that pm25 24h never appears |
| `forecast_scores` | **as built:** one row per matured forecast: `forecast_id` PK, `actual`, `abs_err`, `abs_err_persistence`, `in_interval`, `severe_actual`, `scored_at`, plus `station_id, horizon, target, target_time` copied from the forecast and tied to it by a composite foreign key (migration 007) so model-health queries need no join |
| `skill_rolling` | **as built (new, replaces the rolling part of the original `forecast_scores` idea):** `station_id` (NULL = all stations), `horizon, target, window_end, window_days, n, mae_model, mae_persistence, skill_mae, n_interval, coverage80, n_prob, brier_model, brier_persistence`; UNIQUE NULLS NOT DISTINCT on the key |
| `job_runs` | `job, started_at, finished_at, status, rows, error, skipped JSONB` (per-station skip reasons) |
| `model_registry` | `model_name, model_version, file, sha256, training_window, metrics_source, created_at, active` |

Roles: `api_readonly` (SELECT only on the above), `job_writer` (used by Actions). Credentials only as
secrets. Connection via the Supabase **pooler** string in `DATABASE_URL` (host `…pooler.supabase.com`,
user `postgres.<project-ref>`; session mode port 5432 for Actions jobs, transaction mode 6543 for the API
with prepared statements off; TODO(verify) against the "Connect" panel of your project).

Primary keys on `live_readings` and `live_aqi` are `(station_id, ts)`, which is the UNIQUE(station_id, ts)
upsert key. `forecasts` is unique on `(issue_time, station_id, horizon, target)`; `model_registry` is keyed by
`model_version` and `forecasts.model_version` references it, so the forecast job must register a model before
it can write a forecast.

**Retention (deferred, decide before the free-tier 500 MB limit is a risk).** `forecasts`, `forecast_scores`,
`job_runs` and `live_readings` grow without bound. At roughly 5 forecast rows per station per hour the
forecast tables grow by a few hundred thousand rows a year; that is fine for months, not forever. Neither
database role can DELETE, by design, so any pruning needs a deliberate migration or a separate maintenance
role. Candidate policy to approve later: keep `job_runs` 90 days; keep `forecasts` and `forecast_scores`
12 months, then aggregate into `skill_rolling` (which is small) and delete the detail; keep `live_readings`
and `live_aqi` indefinitely (they are the training data for any future retrain). Measure table sizes after a
month and revisit.

**Indexes for the API (migrations 005 and 007):** `forecasts (station_id, horizon, target, issue_time DESC)`,
`forecasts (station_id, issue_time DESC)`, `forecasts (target_time)`, `forecast_scores (target_time)`,
`live_readings (ts DESC)`, `live_aqi (ts DESC)`, `skill_rolling (horizon, target, window_end DESC)`,
`job_runs (job, started_at DESC)`. The Supabase performance advisor lists them as unused only because the
database is still empty; recheck after real traffic.

## 4. Forecast job rules (as built: `src/live/forecast.py`)

- Reads 408 h per station from `live_readings`/`live_aqi`, masks weather cells flagged `filled:*` when `weather_fill = "none"`, builds
  features through `compute_feature_frame` plus the 24h model's multi-day features (row-based, as in training; see the parity finding).
- One issue hour per run (the newest AQI hour, which must be within the stale limit of now; `--issue-time` replays a past hour).
- A station is **skipped, with the reason in `job_runs.details["skipped"]`**, if: its latest reading is older than 3 h before the
  issue hour; its AQI at the issue hour is missing; it has fewer than 169 AQI rows in the 336 h window; a required feature group
  (AQI, PM2.5, PM10, NO2, SO2, CO, O3) is absent for the whole window; or the share of missing *core* features exceeds the gate in
  `config/forecast_gate.json` (0.22 = 99th percentile over 9,853 validation rows; core = all features except NOx, station weather,
  solar and the station one-hots, the groups the D1 audit showed may be absent). Run status: success / partial / failed (none forecast).
- Models are the frozen 1h/6h LightGBM and 24h hybrid; every artifact is re-hashed against `config/model_hashes.json` and a mismatch
  stops the job. `model_version`s are registered in `aq.model_registry` (`aqi-1h-lgb-v1`, `aqi-6h-lgb-v1`, `aqi-24h-hybrid-v1`);
  `models/registry.json` (Stage 7) will replace the hash file.
- `y_persistence` is written on every row. A forecast is immutable once written (`on conflict do nothing`). No intervals, no P(severe),
  no PM2.5 yet: those models were never persisted (D2 export run still to do).

## 5. API (`backend/main.py`, DB only)

Every response: `data_as_of`, `stale` (true if newest reading > 3 h old), Pydantic models, short
`Cache-Control`, CORS limited to `FRONTEND_ORIGIN`. 24h PM2.5 is never returned.

| Endpoint | Screen | Content |
| :--- | :--- | :--- |
| `GET /api/v1/health` | – | DB reachable, newest reading, newest forecast, last job statuses |
| `GET /api/v1/overview` | Overview | network summary, per-station latest AQI + category, headline forecasts with persistence next to them |
| `GET /api/v1/stations` | Stations | list with coordinates (+ `coords_approximate`) and latest values |
| `GET /api/v1/stations/{id}/forecast?target=aqi\|pm25` | Stations | history + forecasts, persistence, interval/p_severe where they exist |
| `GET /api/v1/alerts/grap` | Operations | current and forecast category per station and GRAP stage. Thresholds read from one config; **TODO(verify)** against the current CAQM GRAP order, and labelled "not an official advisory" |
| `GET /api/v1/model-health` | Model health | rolling 30-day skill vs persistence, coverage, Brier, job status |
| `GET /api/v1/backtest` | Model health | static, from `reports/metrics/headline_metrics.csv` (copied into the image) |

The old static endpoints (`/api/forecasts`, `/api/causal/diwali`, thresholds, episodes) go away. The
Diwali and cost-threshold screens are not in the 4-tab design and leave the live app (they remain
in the README and portfolio). Decision D5.

## 6. Workflows (`.github/workflows/`)

| File | Trigger | Does | Status |
| :--- | :--- | :--- | :--- |
| `probe-sources.yml` | `workflow_dispatch` | reachability, real fields/units and freshness of data.gov.in and OpenAQ from a runner | on `main`; **not run yet** |
| `ingest.yml` | `workflow_dispatch` (cron `10 * * * *` is a TODO) | ingest + Open-Meteo display weather | built; manual until a fresh source |
| `forecast.yml` | `workflow_dispatch`, dry run by default (cron `25 * * * *` is a TODO) | forecast job | built; manual |
| `score.yml` | nightly cron (off the hour) | score matured forecasts; open/refresh a GitHub issue if 24h AQI skill < 0 for 7 consecutive days or a job failed 3 times in a row | Stage 4 |
| `deploy-backend.yml` | push to main touching `backend/**`, dispatch | pytest → build image → push GHCR → `azure/login` (OIDC) → update Container App | Stage 5 |
| `ci.yml` | every push and PR | pytest; frontend lint + type-check | Stage 7 |

Known Actions behaviour: scheduled runs can be late or dropped under load; scheduled workflows in
public repos are auto-disabled after 60 days without repository activity (TODO(verify)); a private
repo has a monthly free-minutes cap that hourly jobs can consume (TODO(verify) current number).
Recommendation: public repo, or a single hourly workflow with two jobs.

## 7. Environment variables and secrets

| Name | Where | Used by |
| :--- | :--- | :--- |
| `DATABASE_URL` (pooler string, writer role) | GitHub secret | ingest, forecast, score |
| `DATABASE_URL_READONLY` | Azure Container App secret; also a GitHub secret for the forecast dry run | API, `forecast.yml` dry run |
| `DATA_GOV_IN_API_KEY` | GitHub secret | probe, ingest (fallback source) |
| `OPENAQ_API_KEY` | GitHub secret | probe, ingest, backfill |
| `LIVE_SOURCE`, `LIVE_FALLBACK`, `LIVE_WEATHER_FILL`, `LIVE_WEATHER_DISPLAY`, `LIVE_ALLOW_UNVERIFIED` | optional GitHub variables | override `config/live.toml` without a commit |
| `FRONTEND_ORIGIN` | Container App env var | API CORS |
| `VITE_API_BASE_URL` | Vercel env var | frontend |
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | GitHub secrets (identifiers, no password) | OIDC login |
| `AZURE_RESOURCE_GROUP`, `AZURE_CONTAINER_APP_NAME` | GitHub variables | deploy |
| `GITHUB_TOKEN` (automatic, `issues: write`, `packages: write`) | Actions | issues, GHCR push |

`.env` is never committed; `.env.example` lists names only.

## 8. Manual steps for you (by stage)

**Before Stage 1:** create a Supabase project (free tier; TODO(verify) its inactivity-pause rule
against an hourly writer); save the DB password in a password manager; copy the pooler connection
string; add `DATABASE_URL` as a GitHub secret.
**Before Stage 2:** register for a data.gov.in API key; register an OpenAQ key; add both as GitHub
secrets; decide public vs private repo (B1/§6).
**Before Stage 5:** create the Azure resources I will list exactly (resource group, Container Apps
environment + Log Analytics workspace, Container App with min replicas 0, an app registration or
user-assigned identity with a GitHub OIDC federated credential on `repo:<owner>/<repo>:ref:refs/heads/main`
scoped to that resource group); make the GHCR package public (the image holds no secrets, data or models)
or provide a read-only pull credential; set the Container App secrets.
**Before Stage 6:** put the exported design files in `docs/design/` (the folder does not exist yet).
**Stage 6 deploy:** import the repo into Vercel, set `VITE_API_BASE_URL`.

## 9. Decisions (settled 2026-10-11)

- **D1 (B1): A first, B only if needed.** Run a validation-only feature-availability audit before the forecast
  job serves any model. Scenarios (same frozen models, validation window Sep 1 – Oct 31 2025, never test):
  1. *data.gov.in source:* NOx masked, temperature/humidity/wind/solar taken from Open-Meteo instead of the
     station sensors.
  2. *OpenAQ source (added by me, because the Stage 1 probe found OpenAQ carries NOx and on-site
     temperature/humidity/wind for 6 of 7 stations):* NOx present, ITO and solar radiation from Open-Meteo.
  Report MAE and skill vs persistence per horizon for each scenario next to the unmodified baseline. **You see
  the audit before anything is decided.** If skill vs persistence is lost, fall back to B (retrain live-feature
  models in Colab). The audit's LightGBM part runs in Colab (no LightGBM locally); the 24h Ridge part can run
  locally.
- **D2 (B3): yes.** Export-only Colab re-fit of the accepted PM2.5 and quantile/classifier configurations,
  saving joblib files plus the conformal pad. Variants and iteration counts come from
  `reports/modeling/pm25/variant_selection.csv` and `probabilistic_metrics.json`; no new selection.
- **D3 (B2): OpenAQ backfill if the overlap check passes, otherwise a cold start.** Backfill the last 10 days with
  `source='openaq'`. The overlap check compares OpenAQ against a trusted reference for values, units and timestamp
  convention, and you see the table before any backfill. OpenAQ needs a key (`X-API-Key`, HTTP 401 without one).
  *Reference changed:* data.gov.in's API host refuses connections from my environment (below), so the
  comparison is OpenAQ vs your own raw CSVs, which contain real overlapping hours.
- **D4: public repo.** Unlimited Actions minutes for the hourly jobs. Cron is auto-disabled after 60 days of no
  repository activity (TODO(verify)); the nightly job's issue/commit activity or a keep-alive covers it.
  The GHCR image may be public, so Azure needs no pull credential.
- **D5: yes.** The Diwali causal and cost-threshold screens leave the live app; they stay in the README and portfolio.
- **D6: yes.** `frontend/CLAUDE.md` is rewritten to the new design tokens in Stage 6.
- **Source rule:** if data.gov.in blocks GitHub's US runners, **OpenAQ becomes the primary live source**; no proxy.
  data.gov.in's API host refused connections from my sandbox (`Connection refused` on 164.100.61.198:443, while
  `www.data.gov.in` answered). That is not proof about GitHub runners, so a probe from a runner is needed
  (needs the key as a repo secret and a pushed probe workflow). Until it runs, treat data.gov.in as unproven.

## 10. Stage checklist

| Stage | Output | Gate | Status |
| :--- | :--- | :--- | :--- |
| 1 | `db/migrations/*.sql`, read-only role, station + backfill script | you apply migrations (I create nothing in the cloud) | **done**; backfill loaded (35,276 readings) |
| 2 | `src/live/ingest.py`, `ingest.yml`, mocked-HTTP tests, source facts replacing the TODOs | one real run from Actions | **code done** (mocked tests); the real run waits for the probe and a fresh source |
| 3 | `src/live/forecast.py`, refactor of the feature builder, **parity test** | parity passes or I report why not | **done**; 24h exact, 1h/6h exact with training's rolling start, small last-digit differences otherwise (reported) |
| 4 | `src/live/score.py`, `score.yml`, issue rules, `src/live/replay.py` | tests with synthetic scores | **code done**; migration 008 (`y_window_update`, `run_type`) must be applied; replay report in `reports/live/` |
| 5 | `backend/main.py`, Dockerfile, `deploy-backend.yml`, Azure resource + secret list | you create resources | not started |
| 6 | 4-tab frontend, Vercel config | lint + type-check pass | frontend rebuilt on branch `tier3/probe-sources` (4 commits, not merged); needs `/api/v1` from Stage 5 |
| 7 | `models/registry.json`, `ci.yml`, README, `docs/TIER_3/TIER_3_LOG.md` | hash-mismatch test | not started (hash check already exists for the forecast job) |

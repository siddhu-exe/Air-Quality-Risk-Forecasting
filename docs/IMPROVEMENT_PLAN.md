# Improvement Plan (for an LLM / coding agent)

Purpose: make this project's results honest, defensible and closer to production quality.
Work through the tasks **in order**. Each task has: why, files, steps, and "done when" checks.
Do not skip "done when". If a check fails, stop and report instead of adjusting the check.

---

## 0. Context you must know first

- **Target:** `aqi_value` in table `aqi_hourly` = official CPCB AQI. It is a **24-hour rolling average** of pollutant sub-indices (see `reports/eda/EDA_REPORT.md:120`, `:301`). Lag-1 autocorrelation ≈ 0.998. Because of this, naive persistence (`pred = aqi_now`) is an extremely strong baseline.
- **AQI coverage:** `aqi_hourly` only has **2025**. Raw pollutants in `caaqms_hourly` cover **2023–2025**.
- **Split** (`reports/phase5_features/split_strategy.md`): train 2025-01-01..08-31, val 2025-09-01..10-31, test 2025-11-01..12-31. The test window is peak winter; train has **no** winter-peak data.
- **Row timestamp = forecast issuance time `t`.** Targets are `target_aqi_{h}h = aqi.shift(-h)` (`src/features/build_features.py:199-201`), so the target time is `t + h`.
- **Pipeline order:** `src/features/build_features.py` → `src/features/export_ml_datasets.py` → `src/models/train_ml_baseline.py` (1h/6h LightGBM) and `src/models/phase_6c_refinement.py` (24h hybrid) → `src/models/phase_7_classification.py` → `src/analysis/cost_aware_threshold_analysis.py`. Causal: `src/analysis/diwali_causal_analysis.py`.
- **Consumers:** `dashboard/app.py` and `backend/main.py` read the files under `reports/classification/`, `reports/causal/` and `reports/classification/metrics/`. If you rename or move any of these files, update both consumers.

### Known defects (evidence)
| ID | Defect | Evidence |
|---|---|---|
| D1 | The 1h model is worse than persistence on RMSE and R² | `data/Artifacts/1h/evaluation_summary_1h.csv` (LGB RMSE 5.08 vs naive 3.82) |
| D2 | README metric table doesn't match the artifacts | README 1h RMSE 3.65 / R² 0.9958 vs CSV 5.08 / 0.9919; 6h RMSE 16.71 vs 15.97 |
| D3 | Cost-optimal threshold tuned on the **test** set | `src/analysis/cost_aware_threshold_analysis.py:39` loads test predictions, then sweeps |
| D4 | Headline recall shown without its precision/FPR cost | `reports/classification/metrics/threshold_operating_points_comparison.csv` (τ=341: precision 54%, FPR 57%) |
| D5 | Lead-time "hit" window is loose (target up to 12h **before** episode counts); time alignment was guessed in comments; no persistence comparison | `src/models/phase_7_classification.py:299-345` |
| D6 | "0% critical miss" (Severe → ≤Moderate) is near-trivial on a smoothed target | `reports/classification/PHASE_7_FINAL_AUDIT.md` |
| D7 | Train excludes previous winters, so trees can't exceed ~347 | split strategy + `reports/modeling/PHASE_6B_24H_REPORT.md` |
| D8 | The causal study can't identify a ban effect: the ban was active in every year studied, pre-trends are violated, the placebo is significant, and SEs ignore station correlation and autocorrelation | `reports/causal/diwali_ban_causal_analysis.md`, `reports/causal/regression_models_summary.csv` |
| D9 | Tests are print scripts with no assertions | `tests/test_bp.py` etc. |
| D10 | Git tracks files that `.gitignore` now excludes (`backups/*.dump`, `.quirq/`, `.xo/`) | `git ls-files backups .quirq .xo` |
| D11 | Docs use inflated language ("100% COMPLIANCE", "Zero Critical Miss Guarantee", "cryptographic integrity") | `reports/**/PHASE_*_AUDIT.md`, README |

### Ground rules
1. **Never** choose models, features, thresholds or blend weights using test-set metrics. Select on validation; evaluate on test **once**.
2. Every metric that appears in README or docs must be produced by a script and read from a file. No hand-typed numbers.
3. Always report naive persistence next to every model metric, plus a **skill score**: `skill = 1 - MAE_model / MAE_persistence` (also an RMSE version).
4. Keep the existing artifact paths unless a task says otherwise (the dashboards depend on them).
5. Don't delete old reports. Move superseded ones to `reports/_archive/` with a one-line note.

---

## Tier 1 — Make results honest (do these first)

### T1.1 Single metrics source of truth  (fixes D1, D2)
- **Create** `src/evaluation/build_metrics_table.py`.
- **Steps:**
  1. Load test predictions: `data/Artifacts/1h/predictions_1h_test.parquet`, `data/Artifacts/6h/predictions_6h_test.parquet`, `reports/modeling/24h/final/final_predictions.parquet`. Inspect the column names first; they differ per file.
  2. For each horizon, compute MAE, RMSE, R², bias, MAE on y≥300, for both the final model **and** persistence (persistence = current AQI column, e.g. `aqi_curr`).
  3. Add `skill_mae` and `skill_rmse` vs persistence.
  4. Add a **block bootstrap** 95% CI on MAE and skill (resample whole days, 1000 iterations, fixed seed).
  5. Write `reports/metrics/headline_metrics.csv` and `reports/metrics/headline_metrics.md` (a markdown table).
- **Then** replace the README "Key Results" table with the content of `headline_metrics.md`, and add one sentence saying persistence is the reference.
- **Done when:** every number in the README results table exists in `headline_metrics.csv`; the 1h row shows negative RMSE skill (that's expected; don't hide it).

### T1.2 Tune alert thresholds on validation, not test  (fixes D3, D4)
- **Edit** `src/analysis/cost_aware_threshold_analysis.py`.
- **Steps:**
  1. Produce **validation-set** 24h predictions with the frozen final model (`models/24h/final/24h_final_model.joblib` plus its imputer, scaler and feature list; the blend = 0.5·persistence + 0.5·ridge, see `phase_6c_refinement.py:359`). Save to `reports/modeling/24h/final/val_predictions.parquet`.
  2. Run the threshold sweep and cost optimization on **validation** only.
  3. Apply the chosen thresholds to test once, and report recall, precision, FPR and the false-alarm count together.
  4. Run the same evaluation for **persistence** as a baseline alert rule.
- **Done when:** `cost_optimal_thresholds_summary.csv` has a `selected_on` column = `val`, and test metrics are in separate columns. The README never states recall without precision.

### T1.3 Fix and baseline the episode / lead-time metric  (fixes D5, D6)
- **Edit** `src/models/phase_7_classification.py`.
- **Steps:**
  1. Make the time alignment explicit: add `issue_time = timestamp` and `target_time = timestamp + h`. Detect episodes on **actual AQI by target_time**. Remove the "assume…" comments.
  2. Hit rule: an alert issued at `issue_time ≤ episode_start` whose `target_time ∈ [episode_start, episode_end]`. Remove the 12h-before tolerance (or make it a named parameter defaulting to 0, and report both).
  3. `lead_time = episode_start - first_valid_issue_time`.
  4. Compute the same hit rate and lead time for **persistence**, and report the delta.
  5. Replace the "critical miss" headline with: Severe recall, Severe precision, and a Very Poor+ confusion summary.
  6. Add a unit test (see T1.5) with a synthetic series where the correct lead time is known.
- **Done when:** the episodes CSV has a `model` column with both `final` and `persistence`; the synthetic test passes.

### T1.4 Reframe the causal analysis  (fixes D8)
- **Edit** `src/analysis/diwali_causal_analysis.py` and `reports/causal/diwali_ban_causal_analysis.md`.
- **Steps:**
  1. Recompute every regression with **standard errors clustered by date** (or Driscoll-Kraay / HAC). Keep station fixed effects. With statsmodels: `.fit(cov_type='cluster', cov_kwds={'groups': df['date']})`.
  2. Use raw daily-mean PM2.5 as the main outcome (AQI is pre-smoothed); keep AQI as a secondary outcome.
  3. Retitle: "Why naive before/after comparisons mislead: Diwali in Delhi". The finding is *methodological*: naive designs give spurious effects (shown by the pre-trend and the placebo).
  4. Remove the causal claims about boundary layer and stubble burning, or label them as hypotheses that need data (fire counts, PBLH) the project doesn't have.
  5. State explicitly: the ban was active in all years studied, so a ban effect is **not identifiable** with this data.
- **Done when:** the report contains no sentence claiming a causal driver without data; regression CSV has a `se_type` column.

### T1.5 Real tests  (fixes D9)
- **Create** `tests/test_alignment.py` and `tests/test_episodes.py` (pytest, with asserts, no DB, no files from `Og Data/`).
  - Alignment: on a toy frame, check `target_aqi_24h[t] == aqi[t+24]`, and that no feature at row t uses data after t (e.g. shift a sentinel spike and check features only change at or after that time).
  - Episodes: a synthetic series with a known episode and known forecasts gives the expected hit and lead time.
- Move the old print scripts to `scripts/checks/` (they aren't tests).
- Add `pytest.ini` with `testpaths = tests`.
- **Done when:** `pytest` passes with ≥5 asserting tests.

### T1.6 Repo hygiene and tone  (fixes D10, D11)
- `git rm -r --cached backups .quirq .xo` (the files are already in `.gitignore`). **Ask the user before committing.**
- Rewrite the README "Key Results", "Key Classification & Alerting Metrics" and audit docs in plain language: remove "guarantee", "100% compliance", "cryptographic", "mathematically rigorous". Add a **Limitations** section near the top covering: smoothed target, persistence is strong, train lacks prior winter, single test window, no forecast meteorology, backtest only.
- **Done when:** `grep -rniE "guarantee|100% compliance|cryptographic" README.md reports docs` returns nothing.

---

## Tier 2 — Make the model genuinely better

### T2.1 Recompute AQI for 2023–2024  (fixes D7)
- **Create** `src/features/compute_cpcb_aqi.py`.
- CPCB method (hourly rolling version):
  - PM2.5, PM10, NO2, SO2, NH3 → 24h rolling mean (µg/m³). CO (mg/m³) and O3 (µg/m³) → 8h rolling mean.
  - Convert each to a sub-index with the CPCB breakpoint table (linear interpolation within the band).
  - AQI = max of sub-indices; valid only if ≥3 pollutants are available **and** at least one is PM2.5 or PM10. Require ≥16 of 24 hours present for 24h averages.
- **Validate** against official 2025 `aqi_hourly`. Report MAE and the share within ±5 in `reports/features/aqi_recompute_validation.md`. **Proceed only if MAE < 10.** If not, debug units first (CO in mg/m³, gases in µg/m³).
- Extend `build_features.py` to use recomputed AQI for 2023–2024 (keep a column `aqi_source ∈ {official, recomputed}`).
- New split: train = 2023-01 .. 2025-08 (includes two winters), val = 2025-09..10, test = 2025-11..12 (unchanged so results are comparable).
- **Done when:** retrained 24h model results are in `headline_metrics.csv` next to the old ones.

### T2.2 Rolling-origin backtest
- Evaluate with expanding-window folds, testing on each winter (e.g. test Nov–Dec 2024 trained on data before it; test Nov–Dec 2025 trained on data before it). Report mean ± std of skill across folds.

### T2.3 Forecast raw PM2.5 as an additional target
- Add `target_pm25_{h}h`. PM2.5 has real hourly dynamics, so model skill vs persistence becomes visible. Optionally derive AQI from forecast PM2.5 plus the observed history.

### T2.4 Exogenous drivers
- Meteorology: Open-Meteo historical API (ERA5) for wind (u/v), boundary layer height, temperature, humidity, precipitation, hourly, at the station coordinates (`stations` table). In backtests, use values at `t+h` as a stand-in for a forecast and **label it clearly as an "oracle weather" upper bound**. Live use would need GFS/Open-Meteo forecast data.
- Fires: NASA FIRMS (VIIRS) daily fire counts in a Punjab/Haryana bounding box, lagged 1–3 days.
- Run an ablation: with vs without each group, on validation.

### T2.5 Probabilistic forecasts
- Train LightGBM quantile models (α = 0.1, 0.5, 0.9), or wrap with split-conformal intervals calibrated on validation.
- Report interval coverage on test (target ≈ 80%) and P(AQI ≥ 401) calibration (a reliability diagram, and the Brier score vs persistence-based probability).

---

## Tier 3 — Production

1. **Live ingestion:** a scheduled job (cron or GitHub Actions) pulls recent hourly data (CPCB/OpenAQ API) into Postgres.
2. **Inference job:** a daily script loads the frozen model, writes forecasts to a `forecasts` table with `issue_time`, `target_time`, `model_version`, and quantiles.
3. **Backend:** `backend/main.py` serves from the `forecasts` table, not static backtest files. Restrict CORS to the frontend origin.
4. **Monitoring:** a nightly job computes realized error vs persistence over the last 30 days and alerts if skill < 0.
5. **Versioning:** MLflow (or a simple `models/registry.json`) for model and data versions; move large data and models out of git (DVC or object storage).
6. **CI:** run `pytest` and `frontend: npm run lint && npm run type-check` on every push.

---

## Output checklist (final state)
- [ ] `reports/metrics/headline_metrics.csv` drives every README number
- [ ] All selection done on validation; test evaluated once
- [ ] Persistence + skill score shown everywhere
- [ ] Alert metrics show recall **and** precision/FPR
- [ ] Lead-time metric fixed, unit-tested, compared to persistence
- [ ] Causal report reframed, clustered SEs
- [ ] `pytest` green with real asserts
- [ ] Limitations section at the top of README
- [ ] (Tier 2) Training includes prior winters; intervals reported

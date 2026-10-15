# Tier 2 audit report

Audit of Tier 2 against `docs/history/IMPROVEMENT_PLAN.md` and `docs/history/TIER_1_IMPROVEMENTS.md`.
The plan's rules: select on validation only and score test once; every quoted number
comes from a script output; always show persistence and skill; keep artifact paths.

## Verdict

Tier 2 was **not done right as delivered**. The T2.1 and T2.2 experiments were sound in
spirit but had leakage and reporting gaps; T2.3–T2.5 had design flaws that made their
headline findings unreliable (including two "negative results" that were partly
artefacts), and the docs/README contradicted the files. All issues below are fixed in
code or text. **T2.3–T2.5 must be rerun in Colab** before their numbers can be quoted;
nothing was trained on the laptop for that part.

## What I checked, and the result

| # | Finding | Severity | Status |
| :--- | :--- | :--- | :--- |
| 1 | **24h label overlap.** Targets are `shift(-h)`, so training rows from the last 24h before a window have labels inside it. No embargo anywhere. | High (leakage) | Fixed: `src/models/splits.py` (`purge_train_tail`, `training_rows`), used by every Tier 2 script. Effect on the 24h hybrid is negligible (below). |
| 2 | **Early-stopping leakage** in the quantile/classifier models (scikit-learn's random internal hold-out on a time series). | High | Fixed: iterations chosen chronologically on validation (`staged_predict`). |
| 3 | **Fake fire results.** `+fires` rows equalled baseline and read as a result. | High (misleading) | Fixed: reported `not_run`. Fires themselves still not run. |
| 4 | **Boundary-layer height is 100% missing before 2024-07-01** but was median-imputed for the first third of training. | High | Fixed: two panels (`full_no_blh`, `blh_window`). |
| 5 | **One linear model** cannot show whether weather helps, so the "weather is useless" conclusion was unsupported. | Medium | Fixed: added `gbm_residual` family next to `ridge_hybrid`. Oracle group never selectable. |
| 6 | **Calendar features fed to trees** in PM2.5/quantile scripts (the project had banned them for the AQI model). Test could be inspected per variant. | High | Fixed: calendar on/off and target form (`level`/`residual`) are validation-selected; test scored once. |
| 7 | **No uncertainty** on rolling-origin and PM2.5 skill; no interval width, persistence-band baseline, Brier CI, constant-rate baseline, or reliability plot. | Medium | Fixed: day-block bootstrap CIs (rolling-origin, PM2.5, Brier diff), widths, baselines, reliability PNG. |
| 8 | **Conformal pad** used a plain percentile. | Low | Fixed: finite-sample CQR level. |
| 9 | **Duplicate persistence row** in `headline_metrics`. | Medium | Fixed (`drop_duplicates`); extended 24h row added. |
| 10 | **Docs/README contradicted the data**: README still said the model "lacks prior winters" and had "no rolling-origin evaluation"; T2.3–T2.5 docs quoted numbers that depended on flaws 1–6. | Medium | Fixed (README, T2.1–T2.5 docs, plan checklist, Tier 2 README). |
| 11 | **Recompute gate** reported only as an overall PASS. | Medium | Fixed: the report now has a by-period table. Jan–Aug MAE is 10.31 (above the gate; Feb–May is 12–15), Sep–Oct 7.98, Nov–Dec 7.26. So 2024 labels are noisier than 2025 labels. |
| 12 | **Import/test breakage**: bare `pytest` and direct `python src/features/build_features.py` failed with `No module named 'src'`. | Medium | Fixed: `pytest.ini` `pythonpath = .` and a `sys.path` shim. 17 tests pass. |
| 13 | **Notebook diverged from the scripts** (own split logic, LightGBM install, `!python` that does not stop on failure, no T2.1/T2.2). | Medium | Rebuilt (below). |

## Before / after (numbers that could be regenerated locally)

All from script outputs; "before" is the pre-audit copy of each file.

| Item | Before | After |
| :--- | :--- | :--- |
| Rolling-origin winter_2024 train rows / MAE skill | 47,855 / +0.0994 | 47,687 / +0.0994 [+0.059, +0.138] |
| Rolling-origin winter_2025 train rows / MAE skill | 103,871 / +0.1119 | 103,703 / +0.1114 [+0.077, +0.145] |
| Rolling-origin mean MAE skill | +0.1056 ± 0.0062 | +0.1054 ± 0.0060 |
| Extended 24h val MAE | 28.8007 | 28.7955 |
| Extended 24h test MAE (persistence 38.342) | 34.0202 | 34.0182 (skill +0.113 [CI in headline table]) |
| `headline_metrics` rows | persistence row duplicated | one row per model, extended row added |

The embargo removes 168 training rows per fold and moves skill by at most 0.0005, so the
earlier T2.1/T2.2 conclusions stand: the 24h hybrid beats persistence by about 10–11% MAE
in both winters (the CIs exclude zero) and extending the training set to 2024 changes the
test MAE by a negligible amount (34.11 → 34.02).

## Not re-measured (needs Colab)

T2.3 PM2.5, T2.4 ablation and T2.5 probabilistic results from the old scripts are
**superseded**; `reports/modeling/{pm25,exogenous,probabilistic}/STALE_RESULTS.md` mark the
leftover files. The old headline findings (PM2.5 24h loses to persistence; weather adds
nothing; probabilities worse than persistence) may or may not survive. An interrupted local
rerun of the PM2.5 script hinted that the 1h result improves (residual+calendar variant won
on validation), but it wrote no file, so it is not a result.

To finish: open `notebooks/tier_2_colab.ipynb` in Colab, set `PROJECT_DIR`, run all (sections 7
and 8 are the slow ones), then fill the "Results" tables of T2.3–T2.5 from the new files and
delete the `STALE_RESULTS.md` markers.

## First Colab run (2026-10-09): rejected, rerun needed

`tier2_reports.zip` came back from Colab but was produced by the **pre-audit code**: the Drive
folder still held the old bundle (`tier_2_colab_bundle.zip`: no `src/models/splits.py`, old
scripts, old notebook). Evidence: the ablation/PM2.5/quantile files have the old schema (no
CIs, variants, widths, `variant_selection.csv` or reliability plot); rolling-origin shows
47,855 training rows (no 24h embargo; the corrected script gives 47,687); the recompute report
has no by-period table. Worse, that run's `final_predictions.parquet` was byte-identical to
`final_predictions_extended.parquet`, i.e. the **frozen 24h predictions on Drive were
overwritten**, which also made its headline table wrong (duplicate persistence rows, frozen
row showing 34.02 instead of 34.11). Nothing from that zip was copied into `reports/`; the
local frozen file is untouched (md5 `a7e9e26f…`).

Fix: `tier_2_colab_bundle_v2.zip` (corrected code plus the genuine frozen predictions) and a
notebook guard that aborts if any corrected-script marker is missing. Unzip the bundle over
the Drive project folder, then rerun the notebook.

## Second Colab run (2026-10-09): partly accepted

`tier2_reports.zip` from the corrected bundle ran the code check and sections 3–6 and 9. It
reproduces the local numbers exactly (rolling-origin, extended 24h and the headline table are
byte-identical to the local files; the headline now has one persistence row and the frozen 24h row
at 34.11, so the frozen predictions on Drive are restored). The new weather ablation was imported
into `reports/modeling/exogenous/` (see T2.4). **Sections 7 (PM2.5) and 8 (quantile) did not run**:
those files in the zip are the first run's old ones (13:33/13:43 timestamps), so T2.3 and T2.5
are still pending and their `STALE_RESULTS.md` markers stay.

## Third Colab run (2026-10-10): accepted except one file

The run used the corrected bundle and produced the first valid PM2.5 and quantile results (T2.3 and T2.5
are now written up; `STALE_RESULTS.md` markers removed). Its rolling-origin, extended-model, ablation and
recompute files are byte-identical to the local ones. **One file was not accepted:**
`final_predictions.parquet` in the zip was again byte-identical to `final_predictions_extended.parquet`
(frozen model replaced by the extended model), so that zip's headline table shows the frozen 24h row as
34.02/0.113 instead of 34.11/0.110. Nothing in the repo writes this file outside
`phase_6c_refinement.py`'s `main()` (not called by the notebook), so the cause is on the Drive side.
The local frozen file is untouched and the local headline table is correct; the zip's headline was not imported.
Mitigation: the notebook now checks the file against its known hash at the start, before the headline step
and at the end, restores it from `data/frozen/` (shipped in `tier_2_patch_v3.zip`), and stops if it cannot.

## Compute profiles for Colab (added 2026-10-10)

`src/models/tuning.py` adds `T2_PROFILE` = `standard` (the accepted configuration, default), `max` (random
hyper-parameter search for the PM2.5, quantile and weather-ablation GBMs with the default config always a
candidate, iteration counts chosen on validation, 10,000 bootstrap resamples) and `smoke` (tiny, only checks
the code paths). Non-standard results are written to `<results folder>/<profile>/`, so the accepted results are
never overwritten. Selection stays validation-only and test is scored once. Status: unit tests for the profile
logic pass. The `smoke` and `max` profiles were then run end to end in Colab (2026-10-10; all four scripts
finished). `max` improved validation MAE by 1–2% for PM2.5 but not test skill, and made the ablation, median-forecast
and Brier results worse on test (see `docs/TIER_2/README.md`). The frozen predictions file kept its hash in both runs.
Caveat: the validation window is much calmer than the winter test window, so more tuning can improve
validation without improving test.

## Open-Meteo rate limiting (fixed 2026-10-10)

`exogenous_drivers.py` fired all 7 station requests at once (two years x 8 variables each), had no retry and
no cache, and refetched on every notebook run, so the free API answered "too many requests" (HTTP 429), more
easily from Colab's shared IPs. Now: sequential requests (one station-year each) with a 2 s pause, retry with
the server's `Retry-After` / a 65 s wait on 429 and backoff on 5xx and network errors, a clear stop when an
hourly/daily quota is exhausted, a per-chunk disk cache (`data/processed/exogenous_cache/`) so reruns and
interrupted runs need no new requests, and the same retry for NASA FIRMS (with the MAP_KEY masked in errors).
Covered by `tests/test_exogenous_fetch.py` (mocked, no network).

## The notebook

`notebooks/tier_2_colab.ipynb` now covers T2.1–T2.5 and the headline table with:
per-section toggles; a `run()` helper that stops on a failing script; a preflight (sklearn
version, required files, rebuild of `features_extended.parquet` from `Og Data/` if missing,
unit tests); the same `splits.py` as the scripts; a freshness check so only outputs written
in the current run are displayed (`SHOW_STALE = True` overrides, and flags them); optional
FIRMS key via Colab secret `FIRMS_MAP_KEY`; and a final table of FRESH/STALE/MISSING outputs
plus a zip download. It was smoke-tested locally with every training toggle off (all cells
execute; the Colab-only calls fall back cleanly); the training sections themselves were not
run.

## Caveats not fixed

- The frozen 1h/6h/24h production artifacts and everything the dashboards read were left
  untouched; the extended model is reported alongside, not substituted.
- The recompute does not meet the MAE < 10 gate in Jan–Aug, so winter-2024 labels are
  noisier than winter-2025 labels.
- Fires are not run (needs a free NASA FIRMS key); station coordinates in
  `exogenous_drivers.py` are approximate; ERA5 is observed weather, not a forecast.
- Only two winters exist for rolling-origin evaluation.
- LightGBM is not installed in the local venv; Tier 2 scripts use scikit-learn
  `HistGradientBoosting` (the notebook does too).

## Files changed

New: `src/models/splits.py`, `tests/test_splits.py`, this report, `STALE_RESULTS.md` markers.
Rewritten: `train_pm25_forecast.py`, `train_quantile_forecast.py`, `ablation_exogenous.py`,
`notebooks/tier_2_colab.ipynb`, T2.3–T2.5 docs. Edited: `retrain_24h_extended.py`,
`rolling_origin_backtest.py`, `build_metrics_table.py`, `compute_cpcb_aqi.py`,
`build_features.py`, `pytest.ini`, T2.1/T2.2 docs, Tier 2 `README.md`, `README.md`,
`CLAUDE.md`, `docs/history/IMPROVEMENT_PLAN.md`.

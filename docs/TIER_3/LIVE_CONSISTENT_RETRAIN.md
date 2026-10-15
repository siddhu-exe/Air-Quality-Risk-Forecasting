# Live-consistent retrain

Status: results in, **decision pending** on which models go live (see Recommendation). Written 2026-10-15.

## Why

The live pipeline recomputes AQI from QC'd pollutants (`compute_aqi`, method `rolling_subindex_mean`). That series sits on
average +5.5 points above the official CPCB AQI the frozen models were trained on, so the frozen official-basis skill
does not carry over (see `docs/TIER_3/PLAN.md`, D1 correction, and `reports/modeling/live_audit/`). The models here are
refit with the **recomputed** AQI as both input and target, on the same feature code, and scored on the live-masked input
view (no NOx, NO, solar everywhere; no ITO temperature, humidity or wind) that the live sources can supply.

## Provenance

- Produced by `notebooks/live_retrain_colab.ipynb` (Colab, 2026-10-15; `models/live/manifest.json` `created` 06:52 UTC).
- Every artifact hash in the three manifests re-computed after download and matches; the six frozen-model hashes recorded in the manifest match `config/model_hashes.json`.
- Libraries pinned: lightgbm 4.7.0, scikit-learn 1.9.0, pandas 2.2.3, numpy 2.1.3 (Python 3.13.16).
- Input matrices (sha256 recorded in the manifest, not re-checkable here because they are rebuilt in Colab): plain `cb2f8999db95`, masked `237e25f67b79`.
- Split: train 2024-01-01..2025-08-31 minus a 24h embargo; validation 2025-09-01..10-31 (LightGBM iteration count only); test 2025-11-01..12-31 scored **once** (`reports/modeling/live_retrain/test_scored.json`).
- New artifact hashes: `config/live_model_hashes.json`. Models: `models/live/`.

| Model | Horizon | Train rows | Features |
| :--- | :--- | ---: | ---: |
| `aqi-1h-lgb-live-v1` | 1h | 97,885 | 131 |
| `aqi-6h-lgb-live-v1` | 6h | 97,396 | 131 |
| `aqi-24h-hybrid-live-v1` | 24h | 95,934 | 49 |

## AQI: retrain vs frozen vs persistence (recomputed AQI)

Skill = 1 - MAE_model / MAE_persistence, persistence on the same recomputed AQI, 95% day-block bootstrap CIs. Source: `reports/modeling/live_retrain/live_retrain_metrics.csv`.
`live-masked` is the same fitted model on the live input view, no refit.

| Horizon | Split | Inputs | Model | Rows | MAE | Persistence MAE | Skill | Skill 95% CI |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1h | val | unmasked | aqi-1h-lgb-live-v1 | 9,947 | 1.535 | 2.240 | +0.315 | [+0.256, +0.370] |
| 1h | val | live-masked | aqi-1h-lgb-live-v1 | 9,947 | 1.553 | 2.240 | +0.307 | [+0.248, +0.363] |
| 1h | val | unmasked | aqi-1h-lgb-v1 (frozen, reference) | 9,947 | 2.137 | 2.240 | +0.046 | [-0.050, +0.136] |
| 1h | test | unmasked | aqi-1h-lgb-live-v1 | 10,221 | 1.528 | 2.330 | +0.344 | [+0.273, +0.400] |
| 1h | test | live-masked | aqi-1h-lgb-live-v1 | 10,221 | 1.540 | 2.330 | +0.339 | [+0.267, +0.395] |
| 1h | test | unmasked | aqi-1h-lgb-v1 (frozen, reference) | 10,221 | 2.527 | 2.330 | -0.084 | [-0.421, +0.127] |
| 6h | val | unmasked | aqi-6h-lgb-live-v1 | 9,907 | 7.691 | 10.668 | +0.279 | [+0.207, +0.343] |
| 6h | val | live-masked | aqi-6h-lgb-live-v1 | 9,907 | 7.817 | 10.668 | +0.267 | [+0.196, +0.331] |
| 6h | val | unmasked | aqi-6h-lgb-v1 (frozen, reference) | 9,907 | 9.944 | 10.668 | +0.068 | [-0.049, +0.172] |
| 6h | test | unmasked | aqi-6h-lgb-live-v1 | 10,181 | 8.402 | 12.153 | +0.309 | [+0.252, +0.355] |
| 6h | test | live-masked | aqi-6h-lgb-live-v1 | 10,181 | 8.474 | 12.153 | +0.303 | [+0.243, +0.351] |
| 6h | test | unmasked | aqi-6h-lgb-v1 (frozen, reference) | 10,181 | 12.716 | 12.153 | -0.046 | [-0.235, +0.092] |
| 24h | val | unmasked | aqi-24h-hybrid-live-v1 | 9,790 | 28.839 | 30.493 | +0.054 | [+0.012, +0.091] |
| 24h | val | live-masked | aqi-24h-hybrid-live-v1 | 9,790 | 28.951 | 30.493 | +0.051 | [+0.005, +0.089] |
| 24h | val | unmasked | aqi-24h-hybrid-v1 (frozen, reference) | 9,790 | 29.195 | 30.493 | +0.043 | [-0.001, +0.080] |
| 24h | test | unmasked | aqi-24h-hybrid-live-v1 | 10,044 | 32.993 | 36.520 | +0.097 | [+0.063, +0.128] |
| 24h | test | live-masked | aqi-24h-hybrid-live-v1 | 10,044 | 33.233 | 36.520 | +0.090 | [+0.051, +0.126] |
| 24h | test | unmasked | aqi-24h-hybrid-v1 (frozen, reference) | 10,044 | 33.602 | 36.520 | +0.080 | [+0.041, +0.114] |

## Calibration side check (validation only)

The alternative to retraining: keep the frozen models and map recomputed AQI to the official scale with an isotonic map fitted on 2025-01..08. Source: `reports/modeling/live_audit/calibration_side_check.csv`.

| Rows | n | MAE before | Bias before | MAE after | Bias after |
| :--- | ---: | ---: | ---: | ---: | ---: |
| fit window 2025-01..08 | 37,896 | 10.28 | +7.91 | 8.06 | -0.00 |
| validation 2025-09..10 | 9,845 | 7.98 | +5.54 | 7.91 | -1.48 |
| Horizon | Basis | Rows scored | Scenario | Rows | MAE | Persistence MAE | Skill | Skill 95% CI | Delta MAE | Delta 95% CI |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: | ---: | :---: |
| 24h | official (baseline, frozen models on official inputs) | all | baseline | 9,413 | 28.462 | 29.942 | +0.049 | [+0.005, +0.086] | +0.000 | [+0.000, +0.000] |
| 24h | official | all | calibrated inputs | 9,413 | 28.751 | 29.942 | +0.040 | [-0.015, +0.087] | +0.289 | [-0.267, +0.841] |
| 24h | calibrated | all | calibrated inputs | 9,413 | 28.334 | 29.641 | +0.044 | [-0.002, +0.082] | -0.449 | [-1.038, +0.099] |
| 1h | official (baseline, frozen models on official inputs) | all | baseline | 9,736 | 1.632 | 2.479 | +0.342 | [+0.274, +0.408] | +0.000 | [+0.000, +0.000] |
| 1h | official | all | calibrated inputs | 9,736 | 7.445 | 2.479 | -2.004 | [-2.359, -1.691] | +5.813 | [+5.313, +6.371] |
| 1h | calibrated | all | calibrated inputs | 9,736 | 2.324 | 2.236 | -0.039 | [-0.137, +0.049] | -5.596 | [-6.186, -5.009] |
| 6h | official (baseline, frozen models on official inputs) | all | baseline | 9,661 | 8.975 | 11.192 | +0.198 | [+0.108, +0.275] | +0.000 | [+0.000, +0.000] |
| 6h | official | all | calibrated inputs | 9,661 | 10.469 | 11.192 | +0.065 | [-0.048, +0.168] | +1.494 | [+1.206, +1.789] |
| 6h | calibrated | all | calibrated inputs | 9,661 | 9.574 | 10.602 | +0.097 | [-0.010, +0.192] | -1.777 | [-2.205, -1.394] |

Compared on validation, the retrain beats calibrated-frozen at every horizon (1h +0.315 vs -0.039; 6h +0.279 vs +0.097; 24h +0.054 vs +0.044), so calibration is not adopted.

## PM2.5 (live-consistent, masked matrix)

HistGradientBoosting, persistence = current PM2.5 (ug/m3). Variant chosen on validation. Source: `reports/modeling/live_pm25/pm25_forecast_metrics.csv`.

| Horizon | Split | N | Variant | Model MAE | Persistence MAE | MAE skill | Skill 95% CI | RMSE skill |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |
| 1h | val | 9,342 | residual | 13.202 | 15.402 | +0.1428 | [+0.118, +0.165] | +0.1505 |
| 1h | test | 9,970 | residual | 24.971 | 31.281 | +0.2017 | [+0.183, +0.219] | +0.1932 |
| 6h | val | 9,231 | level+cal | 25.697 | 38.234 | +0.3279 | [+0.253, +0.384] | +0.3280 |
| 6h | test | 9,862 | level+cal | 64.642 | 101.666 | +0.3642 | [+0.316, +0.407] | +0.3486 |
| 24h | val | 9,178 | residual+cal | 32.096 | 35.814 | +0.1038 | [+0.033, +0.164] | +0.1403 |
| 24h | test | 9,734 | residual+cal | 83.13 | 75.416 | -0.1023 | [-0.238, +0.010] | -0.0792 |

## 24h probabilistic (quantile + conformal)

| Split | N | Raw cov. | Conformal cov. | Pad | Raw width | Conformal width | Persist.-band cov. | Persist.-band width |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| val | 9,790 | 0.753 | 0.800 | 4.301 | 87.86 | 96.46 | 0.853 | 118.18 |
| test | 10,044 | 0.730 | 0.770 | 4.301 | 128.22 | 136.82 | 0.803 | 118.18 |

Full output: `reports/modeling/live_quantile/`.

## Recommendation (for the owner's decision)

- **AQI 1h and 6h: switch to the live-consistent models.** Test skill on the live-masked view is +0.339 (1h) and +0.303 (6h), CIs well above zero, and validation agrees (+0.307, +0.267). The frozen models score negative (1h) or indistinguishable from persistence (6h) on the recomputed basis.
- **AQI 24h: live-consistent hybrid, labelled low-skill.** Test +0.090 live-masked (CI [+0.051, +0.126]); validation +0.051. The frozen hybrid scores +0.080 on unmasked inputs, so the gain is small; the case for switching is basis consistency, not accuracy.
- **PM2.5 1h and 6h: publish as the headline live forecast.** Test skill +0.202 (1h) and +0.364 (6h), CIs above zero, validation agrees. PM2.5 is the measured quantity with no AQI-basis ambiguity.
- **PM2.5 24h: do not publish.** Project rule (no 24h PM2.5 forecast) and the result agrees: test skill -0.102, CI includes zero. The model file is kept in `models/live/pm25/` but must not be wired into the forecast job.
- **24h interval and P(AQI >= 401): do not ship yet.** The conformal 80% interval covers 77.0% on test (target 80%); the severe-event Brier score is not distinguishable from persistence (difference CI includes zero), and the test severe rate (40.8%) is far from validation (3.2%), so the classifier is calibrated on a different regime.
- Caveat for every number above: skill is against persistence on a winter test window with a very different level from validation, and no source is fresh yet, so none of these models has run on live data.

Nothing is wired into `src/live/models.py` or the forecast job yet; the frozen models remain the ones the job loads until this decision is made.

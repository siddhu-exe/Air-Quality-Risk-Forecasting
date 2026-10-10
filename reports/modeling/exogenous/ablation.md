# Exogenous-driver ablation (24h forecast)

Weather = Open-Meteo ERA5. `+weather_oracle` uses weather at t+24 and is an **upper bound
only** (never selected; a real deployment needs forecast weather). Boundary-layer height
is unavailable before 2024-07-01, so it is only used in the `blh_window` panel.
Fire groups need a NASA FIRMS key; they are `not_run` when no `fire_*` columns exist.

## Validation (2025-09-01..10-31) - lower MAE is better

| Panel | Family | Group | # feats | Train n | Val MAE | Val RMSE | Val R² | ΔMAE vs baseline |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| full_no_blh | ridge_hybrid | baseline | 49 | 94,146 | 28.795 | 40.009 | 0.853 | +0.000 |
| full_no_blh | ridge_hybrid | +weather_causal | 61 | 94,146 | 28.753 | 39.495 | 0.856 | -0.042 |
| full_no_blh | ridge_hybrid | +weather_oracle | 67 | 94,146 | 28.67 | 39.368 | 0.857 | -0.126 |
| full_no_blh | ridge_hybrid | +fires | - | 94,146 | not run | not run | not run | - |
| full_no_blh | ridge_hybrid | +weather_causal+fires | - | 94,146 | not run | not run | not run | - |
| full_no_blh | gbm_residual | baseline | 49 | 94,146 | 29.529 | 40.39 | 0.85 | +0.000 |
| full_no_blh | gbm_residual | +weather_causal | 61 | 94,146 | 29.514 | 38.704 | 0.862 | -0.015 |
| full_no_blh | gbm_residual | +weather_oracle | 67 | 94,146 | 28.323 | 37.226 | 0.872 | -1.206 |
| full_no_blh | gbm_residual | +fires | - | 94,146 | not run | not run | not run | - |
| full_no_blh | gbm_residual | +weather_causal+fires | - | 94,146 | not run | not run | not run | - |
| blh_window | ridge_hybrid | baseline | 49 | 65,494 | 28.842 | 40.131 | 0.852 | +0.000 |
| blh_window | ridge_hybrid | +weather_causal | 63 | 65,494 | 28.885 | 39.739 | 0.855 | +0.043 |
| blh_window | ridge_hybrid | +weather_oracle | 70 | 65,494 | 28.717 | 39.547 | 0.856 | -0.125 |
| blh_window | ridge_hybrid | +fires | - | 65,494 | not run | not run | not run | - |
| blh_window | ridge_hybrid | +weather_causal+fires | - | 65,494 | not run | not run | not run | - |
| blh_window | gbm_residual | baseline | 49 | 65,494 | 29.904 | 40.181 | 0.851 | +0.000 |
| blh_window | gbm_residual | +weather_causal | 63 | 65,494 | 29.172 | 38.26 | 0.865 | -0.733 |
| blh_window | gbm_residual | +weather_oracle | 70 | 65,494 | 28.308 | 37.451 | 0.871 | -1.597 |
| blh_window | gbm_residual | +fires | - | 65,494 | not run | not run | not run | - |
| blh_window | gbm_residual | +weather_causal+fires | - | 65,494 | not run | not run | not run | - |

**Best deployable on validation:** `full_no_blh` / `ridge_hybrid` / `+weather_causal` (val MAE 28.753).

## Test (2025-11-01..12-31), scored once

| Panel | Family | Group | Test MAE | Test RMSE | Test R² |
| :--- | :--- | :--- | ---: | ---: | ---: |
| full_no_blh | ridge_hybrid | +weather_causal | 33.89 | 44.52 | 0.373 |
| full_no_blh | ridge_hybrid | baseline | 34.018 | 44.68 | 0.368 |
| - | persistence | aqi_now | 38.342 | 50.747 | 0.185 |

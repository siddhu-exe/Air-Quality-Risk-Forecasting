# Exogenous-driver ablation (24h forecast)

Weather = Open-Meteo ERA5. `+weather_oracle` uses weather at t+24 and is an **upper bound
only** (never selected; a real deployment needs forecast weather). Boundary-layer height
is unavailable before 2024-07-01, so it is only used in the `blh_window` panel.
Fire groups need a NASA FIRMS key; they are `not_run` when no `fire_*` columns exist.
Profile: `max`; `gbm_residual` hyper-parameters tuned on the baseline group of each panel: full_no_blh: `{'learning_rate': 0.08, 'max_leaf_nodes': 31, 'min_samples_leaf': 200, 'l2_regularization': 10.0, 'max_features': 0.7, 'max_iter': 30}`; blh_window: `{'learning_rate': 0.05, 'max_leaf_nodes': 31, 'min_samples_leaf': 20, 'l2_regularization': 0.0, 'max_features': 1.0, 'max_iter': 36}`.

## Validation (2025-09-01..10-31) - lower MAE is better

| Panel | Family | Group | # feats | Train n | Val MAE | Val RMSE | Val R² | ΔMAE vs baseline |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| full_no_blh | ridge_hybrid | baseline | 49 | 94,146 | 28.795 | 40.009 | 0.853 | +0.000 |
| full_no_blh | ridge_hybrid | +weather_causal | 61 | 94,146 | 28.753 | 39.495 | 0.856 | -0.042 |
| full_no_blh | ridge_hybrid | +weather_oracle | 67 | 94,146 | 28.67 | 39.368 | 0.857 | -0.126 |
| full_no_blh | ridge_hybrid | +fires | 53 | 94,146 | 28.795 | 40.009 | 0.853 | +0.000 |
| full_no_blh | ridge_hybrid | +weather_causal+fires | 65 | 94,146 | 28.753 | 39.495 | 0.856 | -0.042 |
| full_no_blh | gbm_residual | baseline | 49 | 94,146 | 28.598 | 39.478 | 0.856 | +0.000 |
| full_no_blh | gbm_residual | +weather_causal | 61 | 94,146 | 28.98 | 39.073 | 0.859 | +0.382 |
| full_no_blh | gbm_residual | +weather_oracle | 67 | 94,146 | 29.023 | 38.703 | 0.862 | +0.425 |
| full_no_blh | gbm_residual | +fires | 53 | 94,146 | 28.764 | 39.733 | 0.855 | +0.166 |
| full_no_blh | gbm_residual | +weather_causal+fires | 65 | 94,146 | 29.144 | 39.167 | 0.859 | +0.546 |
| blh_window | ridge_hybrid | baseline | 49 | 65,494 | 28.842 | 40.131 | 0.852 | +0.000 |
| blh_window | ridge_hybrid | +weather_causal | 63 | 65,494 | 28.885 | 39.739 | 0.855 | +0.043 |
| blh_window | ridge_hybrid | +weather_oracle | 70 | 65,494 | 28.717 | 39.547 | 0.856 | -0.125 |
| blh_window | ridge_hybrid | +fires | 53 | 65,494 | 28.842 | 40.131 | 0.852 | +0.000 |
| blh_window | ridge_hybrid | +weather_causal+fires | 67 | 65,494 | 28.885 | 39.739 | 0.855 | +0.043 |
| blh_window | gbm_residual | baseline | 49 | 65,494 | 28.528 | 39.553 | 0.856 | +0.000 |
| blh_window | gbm_residual | +weather_causal | 63 | 65,494 | 28.666 | 39.036 | 0.86 | +0.138 |
| blh_window | gbm_residual | +weather_oracle | 70 | 65,494 | 28.599 | 39.083 | 0.859 | +0.072 |
| blh_window | gbm_residual | +fires | 53 | 65,494 | 28.528 | 39.553 | 0.856 | +0.000 |
| blh_window | gbm_residual | +weather_causal+fires | 67 | 65,494 | 28.666 | 39.036 | 0.86 | +0.138 |

**Best deployable on validation:** `blh_window` / `gbm_residual` / `baseline` (val MAE 28.528).

## Test (2025-11-01..12-31), scored once

| Panel | Family | Group | Test MAE | Test RMSE | Test R² |
| :--- | :--- | :--- | ---: | ---: | ---: |
| blh_window | gbm_residual | baseline | 34.505 | 45.052 | 0.358 |
| - | persistence | aqi_now | 38.342 | 50.747 | 0.185 |

# Raw PM2.5 forecast metrics

HistGradientBoosting on the extended 2024-2025 feature matrix; persistence = `pm25_now`.
Skill = 1 - metric_model / metric_persistence. The variant (target form, calendar
features) is chosen per horizon on validation MAE only; test is scored once.
Skill CIs are 95% day-block bootstrap intervals.

| Horizon | Split | N | Variant | Model MAE | Persistence MAE | MAE skill | Skill 95% CI | RMSE skill |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |
| 1h | val | 9,241 | residual | 13.239 | 15.39 | +0.1397 | [+0.115, +0.163] | +0.1532 |
| 1h | test | 9,854 | residual | 24.971 | 31.265 | +0.2013 | [+0.181, +0.219] | +0.1941 |
| 6h | val | 9,130 | level+cal | 25.543 | 38.139 | +0.3303 | [+0.258, +0.387] | +0.3194 |
| 6h | test | 9,746 | level+cal | 63.711 | 101.69 | +0.3735 | [+0.322, +0.418] | +0.3526 |
| 24h | val | 9,076 | residual+cal | 31.62 | 35.919 | +0.1197 | [+0.059, +0.178] | +0.1494 |
| 24h | test | 9,615 | residual+cal | 82.285 | 75.292 | -0.0929 | [-0.220, +0.010] | -0.0608 |

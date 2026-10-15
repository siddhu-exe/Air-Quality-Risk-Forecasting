# Raw PM2.5 forecast metrics

Profile: `standard`. HistGradientBoosting on the extended 2024-2025 feature matrix;
persistence = `pm25_now`. Skill = 1 - metric_model / metric_persistence. The variant (target
form, calendar features) is chosen per horizon on validation MAE only;
test is scored once. Skill CIs are 95% day-block bootstrap intervals (1,000 resamples).

| Horizon | Split | N | Variant | Model MAE | Persistence MAE | MAE skill | Skill 95% CI | RMSE skill |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |
| 1h | val | 9,342 | residual | 13.202 | 15.402 | +0.1428 | [+0.118, +0.165] | +0.1505 |
| 1h | test | 9,970 | residual | 24.971 | 31.281 | +0.2017 | [+0.183, +0.219] | +0.1932 |
| 6h | val | 9,231 | level+cal | 25.697 | 38.234 | +0.3279 | [+0.253, +0.384] | +0.3280 |
| 6h | test | 9,862 | level+cal | 64.642 | 101.666 | +0.3642 | [+0.316, +0.407] | +0.3486 |
| 24h | val | 9,178 | residual+cal | 32.096 | 35.814 | +0.1038 | [+0.033, +0.164] | +0.1403 |
| 24h | test | 9,734 | residual+cal | 83.13 | 75.416 | -0.1023 | [-0.238, +0.010] | -0.0792 |

Selected settings (chosen on validation):

- 1h: 400 iterations, `{"learning_rate": 0.05, "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.0, "max_features": 1.0}`
- 6h: 400 iterations, `{"learning_rate": 0.05, "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.0, "max_features": 1.0}`
- 24h: 400 iterations, `{"learning_rate": 0.05, "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.0, "max_features": 1.0}`

# Raw PM2.5 forecast metrics

Profile: `max`. HistGradientBoosting on the extended 2024-2025 feature matrix;
persistence = `pm25_now`. Skill = 1 - metric_model / metric_persistence. The variant (target
form, calendar features) and the hyper-parameters are chosen per horizon on validation MAE only;
test is scored once. Skill CIs are 95% day-block bootstrap intervals (10,000 resamples).

| Horizon | Split | N | Variant | Model MAE | Persistence MAE | MAE skill | Skill 95% CI | RMSE skill |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |
| 1h | val | 9,241 | residual | 13.061 | 15.39 | +0.1513 | [+0.127, +0.173] | +0.1601 |
| 1h | test | 9,854 | residual | 25.041 | 31.265 | +0.1991 | [+0.176, +0.221] | +0.1917 |
| 6h | val | 9,130 | level+cal | 25.238 | 38.139 | +0.3383 | [+0.267, +0.397] | +0.3244 |
| 6h | test | 9,746 | level+cal | 63.435 | 101.69 | +0.3762 | [+0.330, +0.419] | +0.3598 |
| 24h | val | 9,076 | residual+cal | 31.266 | 35.919 | +0.1295 | [+0.068, +0.184] | +0.1620 |
| 24h | test | 9,615 | residual+cal | 82.063 | 75.292 | -0.0899 | [-0.216, +0.016] | -0.0472 |

Selected settings (chosen on validation):

- 1h: 662 iterations, `{"learning_rate": 0.02, "max_leaf_nodes": 127, "min_samples_leaf": 100, "l2_regularization": 1.0, "max_features": 0.7}`
- 6h: 288 iterations, `{"learning_rate": 0.02, "max_leaf_nodes": 127, "min_samples_leaf": 200, "l2_regularization": 1.0, "max_features": 0.7}`
- 24h: 141 iterations, `{"learning_rate": 0.08, "max_leaf_nodes": 63, "min_samples_leaf": 20, "l2_regularization": 100.0, "max_features": 0.7}`

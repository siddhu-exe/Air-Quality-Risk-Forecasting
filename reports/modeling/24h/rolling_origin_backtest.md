# Rolling-origin backtest (24h hybrid, across winters)

Expanding training window, frozen model architecture, test on each winter.
Skill = 1 - metric_model / metric_persistence (positive = beats persistence).

| Fold | Train n | Test n | Test source | Hybrid MAE | Persistence MAE | MAE skill | MAE-skill 95% CI | RMSE skill |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: | :---: | ---: |
| winter_2024 | 47,687 | 10,066 | recomputed | 36.972 | 41.054 | +0.0994 | [+0.059, +0.138] | +0.0961 |
| winter_2025 | 103,703 | 9,800 | official | 34.071 | 38.342 | +0.1114 | [+0.077, +0.145] | +0.1181 |

**Mean MAE skill across folds: +0.1054 ± 0.0060**

**Mean RMSE skill across folds: +0.1071 ± 0.0110**

## Notes

- The winter-2024 fold is scored against the CPCB-*recomputed* AQI (no
  official label exists for 2024), so its absolute errors include the
  reconstruction noise; the winter-2025 fold is scored against official AQI.
- Training rows issued in the 24h before each test window are dropped (24h embargo),
  because their t+24 labels fall inside the test window.
- CIs are 95% day-block bootstrap intervals within each fold (1000 resamples, seed 42).
- Only two folds are possible with the available labelled data (2024, 2025);
  mean ± std over two folds is reported for completeness, not as a stable
  estimate of variance.

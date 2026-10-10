# Probabilistic 24h AQI forecast metrics

Quantile regressors (alpha = 0.1 / 0.5 / 0.9) plus split-conformal calibration of
the 80% interval on validation (finite-sample corrected). Target: `target_aqi_24h`.
Profile: `max`. Iteration counts and hyper-parameters are chosen chronologically on validation; 24h train embargo.
The persistence band is `aqi_now` + empirical 10-90% train residual quantiles,
conformally padded the same way.

## 80% interval coverage and sharpness

| Split | N | Raw cov. | Conformal cov. | Pad | Raw width | Conformal width | Persist.-band cov. | Persist.-band width |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| val | 9,590 | 0.750 | 0.800 | 4.122 | 85.08 | 93.32 | 0.846 | 118.82 |
| test | 9,800 | 0.721 | 0.755 | 4.122 | 130.63 | 138.87 | 0.780 | 118.82 |

## Median forecast (test)

- Median-model MAE **36.22** vs persistence **38.34** (skill +0.0553); pinball loss {'0.1': 11.4, '0.5': 18.11, '0.9': 7.969}.

## P(AQI >= 401) calibration (test)

- Severe rate: train 0.0660, val 0.0236, **test 0.4111**
- Brier score, GBM classifier: **0.2057**
- Brier score, persistence-based: **0.1958**
- Brier score, constant train rate: 0.3612
- Brier difference (model - persistence), 95% day-block CI: [-0.0154, +0.0385] (negative = model better)

Reliability: `reliability_severe.csv` / `reliability_severe_persistence.csv`, diagram in
`reliability_severe.png`.

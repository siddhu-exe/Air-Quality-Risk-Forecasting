# Probabilistic 24h AQI forecast metrics

Quantile regressors (alpha = 0.1 / 0.5 / 0.9) plus split-conformal calibration of
the 80% interval on validation (finite-sample corrected). Target: `target_aqi_24h`.
Profile: `standard`. Iteration counts are chosen chronologically on validation; 24h train embargo.
The persistence band is `aqi_now` + empirical 10-90% train residual quantiles,
conformally padded the same way.

## 80% interval coverage and sharpness

| Split | N | Raw cov. | Conformal cov. | Pad | Raw width | Conformal width | Persist.-band cov. | Persist.-band width |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| val | 9,790 | 0.753 | 0.800 | 4.301 | 87.86 | 96.46 | 0.853 | 118.18 |
| test | 10,044 | 0.730 | 0.770 | 4.301 | 128.22 | 136.82 | 0.803 | 118.18 |

## Median forecast (test)

- Median-model MAE **35.16** vs persistence **36.52** (skill +0.0372); pinball loss {'0.1': 11.08, '0.5': 17.581, '0.9': 7.631}.

## P(AQI >= 401) calibration (test)

- Severe rate: train 0.0656, val 0.0317, **test 0.4080**
- Brier score, GBM classifier: **0.1891**
- Brier score, persistence-based: **0.1943**
- Brier score, constant train rate: 0.3588
- Brier difference (model - persistence), 95% day-block CI: [-0.0243, +0.0165] (negative = model better)

Reliability: `reliability_severe.csv` / `reliability_severe_persistence.csv`, diagram in
`reliability_severe.png`.

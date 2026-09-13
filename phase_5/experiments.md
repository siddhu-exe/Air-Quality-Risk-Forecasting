# Phase 5: Baseline Experiments & Feature Ranking Analysis

## 1. Overview & Experimental Setup

Phase 5 evaluates baseline forecasting heuristics and quantifies feature predictive power across 57,946 hourly observations in 2025 across 7 continuous air quality monitoring stations in Delhi.

The evaluation benchmarks three distinct horizons:
- **1-Hour Horizon ($h=1$):** Real-time immediate risk assessment.
- **6-Hours Horizon ($h=6$):** Intra-day operational warning and intervention window.
- **24-Hours Horizon ($h=24$):** Next-day planning and CAQM GRAP regulatory stage activation.

---

## 2. Benchmark Baseline Evaluation Matrix

Baseline models were evaluated across three chronological partitions (Train, Validation, Test) as well as the full annual sequence.

```
Model Summary Across Partitions & Horizons:
┌───────────────────────────┬─────────┬────────┬───────────┬───────────┬─────────┬──────────────┐
│ Model                     │ Split   │ Horizon│ MAE       │ RMSE      │ R²      │ Extr. MAE    │
├───────────────────────────┼─────────┼────────┼───────────┼───────────┼─────────┼──────────────┤
│ Naive Persistence         │ Test    │ 1h     │  2.40     │  3.82     │ 0.9955  │  2.26        │
│ 24h Moving Average        │ Test    │ 1h     │ 21.47     │ 28.69     │ 0.7426  │ 20.09        │
│ 24h Seasonal Persistence  │ Test    │ 1h     │ 39.02     │ 51.77     │ 0.1633  │ 35.74        │
├───────────────────────────┼─────────┼────────┼───────────┼───────────┼─────────┼──────────────┤
│ Naive Persistence         │ Test    │ 6h     │ 12.72     │ 17.58     │ 0.9024  │ 11.95        │
│ 24h Moving Average        │ Test    │ 6h     │ 28.40     │ 37.72     │ 0.5503  │ 26.44        │
│ 24h Seasonal Persistence  │ Test    │ 6h     │ 38.85     │ 51.52     │ 0.1619  │ 35.79        │
├───────────────────────────┼─────────┼────────┼───────────┼───────────┼─────────┼──────────────┤
│ Naive Persistence         │ Test    │ 24h    │ 38.34     │ 50.75     │ 0.1848  │ 35.32        │
│ 24h Seasonal Persistence  │ Test    │ 24h    │ 38.34     │ 50.75     │ 0.1848  │ 35.32        │
│ 24h Moving Average        │ Test    │ 24h    │ 44.99     │ 58.71     │ -0.0877 │ 40.74        │
└───────────────────────────┴─────────┴────────┴───────────┴───────────┴─────────┴──────────────┘
```

### Key Insights from Baseline Benchmarking
1. **At $h=1$ hour:** Naive persistence achieves near-perfect tracking ($\text{MAE} \approx 2.40\text{--}2.81$, $R^2 \ge 0.995$) due to the mathematical formulation of reported AQI as a 24-hour moving buffer.
2. **At $h=6$ hours:** Naive persistence remains relatively strong ($\text{MAE} \approx 12.72$, $R^2 \approx 0.902$ on Test), while moving averages degrade ($\text{MAE} \approx 28.40$).
3. **At $h=24$ hours:** All heuristic baselines degrade drastically on the peak Winter test set ($\text{MAE} \approx 38.34$, $R^2 \approx 0.1848$), confirming that simple persistence cannot anticipate multi-day atmospheric stagnation, rapid inversion collapses, or emission surges.

---

## 3. Feature Group Predictive Ranking

Feature predictive power was evaluated by calculating bivariate Pearson correlations with future targets across all 124 engineered features.

### Mean Group Predictive Power

| Feature Group | Feature Count | Mean $|r|$ ($h=1$) | Mean $|r|$ ($h=6$) | Mean $|r|$ ($h=24$) | Top Group Feature | Top Pearson $r$ ($h=1$) |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **Group A: Recent AQI Lags** | 10 | **0.9295** | **0.9166** | **0.8667** | `aqi_curr` | +0.9984 |
| **Group G: Cross-Station Spatial** | 6 | **0.8903** | **0.8900** | **0.8432** | `network_mean_aqi_lag_1h` | +0.9577 |
| **Group C: Causal Rolling Statistics** | 32 | **0.7728** | **0.7699** | **0.7238** | `aqi_roll_mean_3h` | +0.9972 |
| **Group B: Pollutant Lags** | 35 | **0.4327** | **0.4355** | **0.4126** | `pm25_curr` | +0.8117 |
| **Group E: Seasonality Indicators** | 4 | **0.4140** | **0.4143** | **0.4153** | `is_winter` | +0.6277 |
| **Group F: Meteorology** | 24 | **0.2081** | **0.2095** | **0.2103** | `temp_roll_mean_24h` | -0.6541 |
| **Group D: Temporal & Cyclical** | 13 | **0.1716** | **0.1717** | **0.1749** | `cos_doy` | +0.7696 |

---

## 4. Top 10 Individual Predictive Features per Horizon

### 1-Hour Ahead ($h=1$)
1. `aqi_curr` (Group A): $r = +0.9984$
2. `aqi_roll_mean_3h` (Group C): $r = +0.9972$
3. `aqi_roll_min_3h` (Group C): $r = +0.9968$
4. `aqi_lag_1h` (Group A): $r = +0.9966$
5. `aqi_roll_max_3h` (Group C): $r = +0.9963$
6. `aqi_roll_mean_6h` (Group C): $r = +0.9946$
7. `aqi_lag_2h` (Group A): $r = +0.9944$
8. `aqi_roll_min_6h` (Group C): $r = +0.9935$
9. `aqi_roll_max_6h` (Group C): $r = +0.9921$
10. `aqi_lag_3h` (Group A): $r = +0.9919$

### 6-Hours Ahead ($h=6$)
1. `aqi_curr` (Group A): $r = +0.9861$
2. `aqi_roll_min_3h` (Group C): $r = +0.9837$
3. `aqi_roll_mean_3h` (Group C): $r = +0.9835$
4. `aqi_lag_1h` (Group A): $r = +0.9829$
5. `aqi_roll_max_3h` (Group C): $r = +0.9820$
6. `aqi_lag_2h` (Group A): $r = +0.9794$
7. `aqi_roll_mean_6h` (Group C): $r = +0.9792$
8. `aqi_roll_min_6h` (Group C): $r = +0.9792$
9. `aqi_lag_3h` (Group A): $r = +0.9758$
10. `aqi_roll_max_6h` (Group C): $r = +0.9758$

### 24-Hours Ahead ($h=24$)
1. `aqi_curr` (Group A): $r = +0.9151$
2. `aqi_roll_min_3h` (Group C): $r = +0.9124$
3. `aqi_roll_mean_3h` (Group C): $r = +0.9120$
4. `aqi_lag_1h` (Group A): $r = +0.9111$
5. `aqi_roll_max_3h` (Group C): $r = +0.9106$
6. `aqi_roll_min_6h` (Group C): $r = +0.9087$
7. `aqi_roll_mean_6h` (Group C): $r = +0.9078$
8. `aqi_lag_2h` (Group A): $r = +0.9076$
9. `aqi_roll_max_6h` (Group C): $r = +0.9047$
10. `aqi_lag_3h` (Group A): $r = +0.9042$

---

## 5. Architectural Recommendations for Phase 6 Modeling

1. **Short Horizons ($h=1$ to $h=3$):** Autoregressive and rolling features (Groups A & C) carry near-deterministic weight. Model capacity should focus on boundary regularization rather than complex non-linear interactions.
2. **Medium Horizons ($h=6$):** Photochemical precursor signals (Group B: $\text{NO}_x, \text{O}_3, \text{PM}_{2.5}$) and spatial airshed indicators (Group G) provide critical deviation signals beyond simple persistence.
3. **Long Horizons ($h=24$):** Macro-meteorological trends (Group F: Temperature and Humidity rolling means) and seasonal indicators (Group E & D: `is_winter`, `cos_doy`) are essential to overcome the collapse of simple persistence and capture multi-day severe episode buildup.

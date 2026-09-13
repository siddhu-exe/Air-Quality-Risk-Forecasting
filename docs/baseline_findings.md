# Phase 5 Baseline Benchmarking & Feature Ranking Findings

*This document summarizes the core empirical and engineering results from Phase 5 (Feature Engineering & Baseline Modeling).*

---

## 1. Multi-Horizon Forecasting Targets

Targets are future Air Quality Index values defined as $Y_{s, t+h} = \text{AQI}_{s, t+h}$:
- **1-Hour Ahead ($h=1$):** Real-time immediate risk alerts. Network availability: **99.20%** (57,483 valid samples).
- **6-Hours Ahead ($h=6$):** Actionable intra-day municipal intervention window. Network availability: **98.35%** (56,989 valid samples).
- **24-Hours Ahead ($h=24$):** Next-day planning and CAQM GRAP regulatory action. Network availability: **96.21%** (55,750 valid samples).

---

## 2. 7-Group Feature Taxonomy (124 Causal Features)

1. **Group A: Recent AQI Lags (10 Features):** `aqi_curr`, `aqi_lag_1h` through `aqi_lag_168h` (1 week).
2. **Group B: Pollutant Lags (35 Features):** Current & lags (1h, 6h, 12h, 24h) for $\text{PM}_{2.5}, \text{PM}_{10}, \text{NO}_2, \text{NO}_x, \text{SO}_2, \text{CO}, \text{O}_3$.
3. **Group C: Causal Rolling Statistics (32 Features):** Trailing mean, std, min, max (3h, 6h, 12h, 24h) for $\text{AQI}$ and $\text{PM}_{2.5}$ strictly over $[t-W+1, t]$.
4. **Group D: Temporal & Cyclical (13 Features):** `hour`, `day_of_week`, `month`, `day_of_year`, `is_weekend`, plus sine/cosine circular encodings.
5. **Group E: IMD Seasonality Indicators (4 Features):** `is_winter`, `is_summer`, `is_monsoon`, `is_post_monsoon`.
6. **Group F: Usable Meteorology (24 Features):** Current, lagged (1h, 6h, 24h), and rolling means (6h, 24h) for Temperature, Humidity, Wind Speed, Solar Radiation.
7. **Group G: Cross-Station Spatial Network (6 Features):** Leave-one-out network mean, max, min for $\text{AQI}$ and $\text{PM}_{2.5}$ at lag-1h, plus top-correlated neighbor station lag-1h.

---

## 3. Strict Leakage Prevention

- **Rolling Aggregates:** Evaluated strictly on trailing intervals $[t-W+1, t]$ (`center=False`).
- **Spatial Network Signals:** Evaluated strictly on lag-1h observations ($\le t-1$) with target station subtracted.
- **Warm-Up Buffer:** 2024 records loaded to populate lag-168h and rolling 24h stats for early Jan 2025 without row drops.
- **Partition Independence:** Chronological splits prevent data leakage across time.

---

## 4. Benchmark Baseline Evaluation Matrix

```text
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

---

## 5. Feature Predictive Power by Group

| Feature Group | Count | Mean $|r|$ ($h=1$) | Mean $|r|$ ($h=6$) | Mean $|r|$ ($h=24$) | Top Group Feature | Top $r$ ($h=1$) |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **Group A: Recent AQI Lags** | 10 | **0.9295** | **0.9166** | **0.8667** | `aqi_curr` | +0.9984 |
| **Group G: Cross-Station Spatial** | 6 | **0.8903** | **0.8900** | **0.8432** | `network_mean_aqi_lag_1h` | +0.9577 |
| **Group C: Causal Rolling Statistics** | 32 | **0.7728** | **0.7699** | **0.7238** | `aqi_roll_mean_3h` | +0.9972 |
| **Group B: Pollutant Lags** | 35 | **0.4327** | **0.4355** | **0.4126** | `pm25_curr` | +0.8117 |
| **Group E: Seasonality Indicators** | 4 | **0.4140** | **0.4143** | **0.4153** | `is_winter` | +0.6277 |
| **Group F: Meteorology** | 24 | **0.2081** | **0.2095** | **0.2103** | `temp_roll_mean_24h` | -0.6541 |
| **Group D: Temporal & Cyclical** | 13 | **0.1716** | **0.1717** | **0.1749** | `cos_doy` | +0.7696 |

---

## 6. Guidance for Phase 6 Modeling

1. **Short Horizons ($h=1$ to $h=3$):** Autoregressive and rolling features (Groups A & C) carry near-deterministic weight. Focus on simple regularization and boundary clipping.
2. **Medium Horizons ($h=6$):** Precursor chemical ratios (Group B: $\text{NO}_x, \text{O}_3, \text{PM}_{2.5}$) and spatial airshed indicators (Group G) provide critical deviation signals beyond simple persistence.
3. **Long Horizons ($h=24$):** Macro-meteorological trends (Group F: Temperature and Humidity rolling means) and seasonal indicators (Group E & D: `is_winter`, `cos_doy`) are essential to overcome the collapse of simple persistence and capture multi-day severe episode buildup.

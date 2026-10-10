# CPCB AQI recompute validation (2025)

Method: `rolling_subindex_mean`. Ground truth: official station-level `aqi_hourly` xlsx for 2025.
Script: `src/features/compute_cpcb_aqi.py`.

## Summary

| Metric | Value |
|---|---|
| Matched hours | 57,755 |
| MAE | 9.382 |
| Median absolute error | 6.389 |
| Bias (recomputed - official) | +6.485 |
| Share within +/-5 | 42.2% |
| Share within +/-10 | 65.9% |
| Gate (MAE < 10) | **PASS** |

## MAE by station

| Station | MAE |
|---|---|
| Anand Vihar | 10.21 |
| Bawana | 8.98 |
| Dwarka-Sector 8 | 10.51 |
| ITO | 6.15 |
| Jahangirpuri | 10.12 |
| Punjabi Bagh | 10.58 |
| R K Puram | 9.15 |

## MAE by period

The overall gate is met, but only because the Sep-Dec months are easier; the
Jan-Aug error is above 10 (largest in Feb-May).

| Period | Matched hours | MAE | Bias |
|---|---|---|---|
| Jan-Aug (before validation window) | 37,807 | 10.31 | +7.91 |
| Sep-Oct (validation window) | 9,845 | 7.98 | +5.54 |
| Nov-Dec (test window) | 10,103 | 7.26 | +2.06 |

## MAE by month

| Month | MAE |
|---|---|
| 1 | 6.5 |
| 2 | 11.9 |
| 3 | 14.69 |
| 4 | 13.65 |
| 5 | 14.99 |
| 6 | 7.93 |
| 7 | 6.32 |
| 8 | 5.83 |
| 9 | 6.42 |
| 10 | 9.52 |
| 11 | 8.12 |
| 12 | 6.44 |

## Known limitations

- The residual bias is positive and concentrated at high AQI; official values
  can also contain isolated glitches (e.g. an official spike to 314 while the
  raw PM2.5 is 28 ug/m3). Reconstructed AQI is therefore a good training target
  but not a drop-in replacement for the official series.
- 2023 raw data is only available for Dwarka-Sector 8; the other stations start
  in 2024.

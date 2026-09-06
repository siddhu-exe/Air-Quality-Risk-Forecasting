# Column Mapping Report

Generated from empirical data in `schema_report.csv`.

## Mapped Columns (CAAQMS)
| Raw Column Name | Canonical Target Column | Target Mapping Status |
| --- | --- | --- |
| `AT (°C)` | `temp_c` | Mapped |
| `BP (mmHg)` | `bp_mmhg` | Mapped |
| `Benzene (µg/m³)` | `benzene_ugm3` | Mapped |
| `CO (mg/m³)` | `co_mgm3` | Mapped |
| `Date` | `ts` (base) | Handled specifically in pipeline |
| `Eth-Benzene (µg/m³)` | `eth_benzene_ugm3` | Mapped |
| `MP-Xylene (µg/m³)` | `mp_xylene_ugm3` | Mapped |
| `NH3 (µg/m³)` | `nh3_ugm3` | Mapped |
| `NO (µg/m³)` | `no_ugm3` | Mapped |
| `NO2 (µg/m³)` | `no2_ugm3` | Mapped |
| `NOx (ppb)` | `nox_ppb` | Mapped |
| `O Xylene (µg/m³)` | `o_xylene_ugm3` | Mapped |
| `Ozone (µg/m³)` | `ozone_ugm3` | Mapped |
| `PM10 (µg/m³)` | `pm10` | Mapped |
| `PM2.5 (µg/m³)` | `pm25` | Mapped |
| `RF (mm)` | `rf_mm` | Mapped |
| `RH (%)` | `rh_pct` | Mapped |
| `SO2 (µg/m³)` | `so2_ugm3` | Mapped |
| `SR (W/mt2)` | `sr_wm2` | Mapped |
| `TOT-RF (mm)` | `tot_rf_mm` | Mapped |
| `Timestamp` | `ts` | Mapped |
| `Toluene (µg/m³)` | `toluene_ugm3` | Mapped |
| `VWS (m/s)` | `vws_ms` | Mapped |
| `WD (deg)` | `wd_deg` | Mapped |
| `WS (m/s)` | `ws_ms` | Mapped |
| `Xylene (µg/m³)` | `xylene_ugm3` | Mapped |

## AQI Wide-Format Hours (XLSX files)

24 distinct hour columns found (e.g. `00:00:00`, `01:00:00`).
They are automatically unpivoted in staging to the canonical `ts` and `aqi` columns.

## Summary
- **Total Non-Time Raw Columns Found:** 26
- **Mapped / Handled:** 26
- **Unmapped (Discarded):** 0
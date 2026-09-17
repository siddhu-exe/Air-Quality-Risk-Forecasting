# [INTERNAL WORKING NOTE] Causal Findings: Delhi Diwali Firecracker Ban Policy vs Seasonal Inversion

**Document Version:** 1.0  
**Status:** Finalized  
**Date:** September 17, 2026  

---

## 1. Executive Summary

This empirical analysis evaluates whether the Delhi firecracker ban policy during Diwali (2023, 2024, 2025) produced a measurable reduction in ambient Air Quality Index (AQI), using CAAQMS/AQI database records across 7 monitoring stations in Delhi.

### Key Empirical Findings
- **Pre-Trends Violation:** The parallel pre-trends identification assumption is severely violated. Over the 14 days prior to Diwali 2025, Delhi daily mean AQI escalated at **$+20.38$ points/day ($p < 0.001, R^2 = 0.770$)**, rising from 69.8 to 334.3 due to seasonal autumn-to-winter meteorological transitions.
- **Interrupted Time Series Verdict:** When controlling for pre-existing trajectories, temperature, wind speed, humidity, and station fixed effects, the immediate post-Diwali level shift is **$-10.59$ AQI points ($\text{SE} = 13.28, p = 0.425, 95\%\text{ CI: } [-36.61, +15.43]$)**, statistically indistinguishable from zero.
- **Placebo Falsification:** An in-time placebo test on a non-event date 30 days prior (September 20, 2025) yields a statistically significant pseudo-treatment shift of **$+24.26$ AQI points ($p < 0.001$)**, confirming that naive pre/post comparisons capture seasonal drift rather than policy impact.
- **Acute Combustion vs Persistent Inversion:** Hourly telemetry reveals an acute 6–12 hour combustion burst on Diwali night ($\text{PM}_{2.5}$ peaking at $960.7\ \mu\text{g/m}^3$ and $\text{SO}_2$ tracer surging 5.3x–7.9x to $74\text{--}80\ \mu\text{g/m}^3$), indicating substantial short-term ban non-compliance. However, emissions dispersed within 18–24 hours; sustained multi-week winter pollution is driven by planetary boundary layer compression (<300m), thermal inversion, calm winds (<0.8 m/s), and transboundary crop residue burning.

---

## 2. Policy Timeline & Data Coverage

```
+---------------------------------------------------------------------------------------------------------------+
| Year | Diwali Date | Delhi Policy Status          | Mumbai Policy Status        | Repository Data Coverage    |
+---------------------------------------------------------------------------------------------------------------+
| 2023 | 2023-11-12  | Complete Blanket Ban (DPCC)  | Restricted Windows (8-10 PM)| Dwarka-Sector 8 (Hourly)    |
| 2024 | 2024-10-31  | Complete Blanket Ban (DPCC)  | No Blanket Ban (Permitted)  | 7 Stations CAAQMS (Hourly)  |
| 2025 | 2025-10-20  | Complete Blanket Ban (DPCC)  | No Blanket Ban (Permitted)  | 7 Stations CAAQMS + AQI     |
+---------------------------------------------------------------------------------------------------------------+
```

*Data Constraint:* Mumbai data exists in the repository exclusively for **January–July 2026** (`Og Data/Mumbai data/`). Because 2023–2025 Mumbai records are unpopulated, external Difference-in-Differences against Mumbai was precluded, and internal quasi-experimental controls (ITS, station fixed effects, placebo testing) were executed.

---

## 3. Master Econometric Regression Results

Evaluated across a $\pm 14$-day window around Diwali 2025 (October 6 to November 3, 2025) with cluster-robust standard errors clustered at the monitoring station level:

| Model Specification | Estimated Effect ($\beta$) | Robust SE | $t$-statistic | $p$-value | 95% Confidence Interval | $R^2$ | $N$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Pre-Trend Linear Slope** | $+20.38$ pts/day | $1.32$ | $15.40$ | $< 0.001$ | $[+17.78, +22.97]$ | $0.770$ | 94 |
| **Model 1 (Naive Bivariate OLS)** | $+135.57$ | $10.12$ | $13.39$ | $< 0.001$ | $[+115.73, +155.41]$ | $0.465$ | 192 |
| **Model 2 (Station Fixed Effects)** | $+136.35$ | $10.57$ | $12.90$ | $< 0.001$ | $[+115.63, +157.07]$ | $0.528$ | 192 |
| **Model 3 (Meteo Controls + FE)** | $+114.53$ | $11.61$ | $9.87$ | $< 0.001$ | $[+91.78, +137.29]$ | $0.722$ | 164 |
| **Model 4 (Interrupted Time Series)** | **$-10.59$** | **$13.28$** | **$-0.80$** | **$0.425$** | **$[-36.61, +15.43]$** | **$0.870$** | 164 |
| **Model 5 (Placebo Falsification)** | $+24.26$ | $4.24$ | $5.72$ | $< 0.001$ | $[+15.94, +32.57]$ | $0.540$ | 195 |

---

## 4. Hourly Combustion Chemistry vs Atmospheric Dispersion

```
===============================================================================================================
Metric / Pollutant                Diwali 2024 (Oct 31, 2024)            Diwali 2025 (Oct 20, 2025)
---------------------------------------------------------------------------------------------------------------
Pre-Festival Daytime Baseline PM2.5    108.9 µg/m³ (14:00)                  120.5 µg/m³ (14:00)
Diwali Night Peak PM2.5                612.9 µg/m³ (Nov 01 01:00)           960.7 µg/m³ (Oct 21 00:00)
Particulate Surge Multiplier           5.63x Baseline                       7.97x Baseline
Pre-Festival Daytime Baseline SO2      10.12 µg/m³ (14:00)                   13.76 µg/m³ (14:00)
Diwali Night Peak SO2 (Tracer)         80.06 µg/m³ (Nov 01 00:00)           73.50 µg/m³ (Oct 20 23:00)
SO2 Chemical Surge Multiplier          7.91x Baseline                       5.34x Baseline
Time to Return to Baseline Trajectory  ~18 Hours (Nov 01 18:00)             ~20 Hours (Oct 21 20:00)
===============================================================================================================
```

---

## 5. Artifact Index

- **Master Report:** `reports/causal/diwali_ban_causal_analysis.md`
- **Script:** `src/analysis/diwali_causal_analysis.py`
- **Data CSVs:** `reports/causal/*.csv`
- **Figures:** `reports/causal/figures/` (01–04)

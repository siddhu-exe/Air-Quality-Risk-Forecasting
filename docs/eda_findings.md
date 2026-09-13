# Phase 4: Exploratory Data Analysis (EDA) Summary

This document provides a concise architectural and statistical reference for the findings uncovered during **Phase 4 (Exploratory Data Analysis)** of the Air Quality Risk Forecasting project.

---

## 1. Executive Summary

Phase 4 conducted a read-only, SQL-first statistical analysis against the curated PostgreSQL database (`air_quality_db`), auditing 162,096 CAAQMS hourly observations and 57,946 AQI records across 7 monitoring stations in Delhi (2023–2026).

All 12 required analytical dimensions were evaluated, yielding an 11-figure visual suite in `reports/eda/figures/`, comprehensive metric CSVs in `reports/eda/`, and a detailed formal report in `reports/eda/EDA_REPORT.md`.

---

## 2. Key Statistical Insights

### A. Airshed Spatial Synchronization
- **Finding:** Pairwise cross-station Pearson correlation across all 7 Delhi stations is $r \ge 0.92$ for AQI and $r \ge 0.84$ for $\text{PM}_{2.5}$.
- **Significance:** Delhi NCR acts as a unified, regionally synchronized airshed driven by macro-scale planetary boundary layer dynamics rather than isolated micro-climates. Spatial neighbor inputs will provide powerful regularization for downstream models.

### B. Diurnal Atmospheric Decoupling
- **$\text{PM}_{2.5}$**: Distinct bimodal cycle with peaks at **07:00** and **23:00** (~$155\ \mu\text{g/m}^3$), driven by morning traffic rush hours and nocturnal planetary boundary layer (PBL) compression.
- **$\text{O}_3$ (Ozone)**: Single photochemical peak at **14:00** (~$37\text{--}45\ \mu\text{g/m}^3$) driven by solar radiation and $\text{NO}_x$ photolysis.
- **AQI**: Shows a flattened diurnal profile because reported AQI is mathematically computed as a 24-hour moving average buffer.

### C. Autoregressive Persistence & Diurnal Harmonics
- **AQI**: Autocorrelation is near-unity at lag-1 ($r \approx 0.998$), maintaining $r \approx 0.77$ out to lag-168 (1 week).
- **$\text{PM}_{2.5}$**: Strong short-term persistence at lag-1 ($r \approx 0.956$), dipping at lag-12 ($r \approx 0.610$), followed by a sharp **rebound at lag-24 ($r \approx 0.748$)** due to 24-hour diurnal harmonic resonance.

### D. Extreme Winter Pollution Episodes
- **123 discrete severe episodes** ($\text{AQI} \ge 400$ lasting $\ge 6$ consecutive hours) were identified.
- Heavily clustered in **November through January** (Winter and Post-Monsoon).
- Longest single uninterrupted severe event lasted **405 continuous hours** at Bawana in November 2025.

### E. Meteorological Feature Usability
- **High Usability (Recommended for ML):**
  - **Temperature:** $r = -0.521$ (Spearman $\rho = -0.562$) vs $\text{PM}_{2.5}$.
  - **Relative Humidity:** $r = +0.272$ vs $\text{PM}_{2.5}$ (promotes secondary aerosol condensation).
  - **Wind Speed:** $r = -0.158$ (Spearman $\rho = -0.292$) vs $\text{PM}_{2.5}$ (advective dispersion).
  - **Solar Radiation:** $r = -0.157$ vs $\text{PM}_{2.5}$.
- **Exclusions / Cautionary Notes:**
  - **Rainfall:** 56.6% missing (sparse monsoon-only signal).
  - **Xylene:** 100% missing across the network.
  - **ITO Station:** Lacks meteorological sensors (100% missing weather parameters).

---

## 3. Visual Suite Index (`reports/eda/figures/`)

1. `01_aqi_timeseries.png` — Multi-year temporal evolution & severe episode zones.
2. `02_diurnal_profiles.png` — 24-hour diurnal cycles of pollutants vs AQI buffer.
3. `03_monthly_heatmap.png` — Monthly seasonal progression matrix.
4. `04_seasonal_distributions.png` — Boxplots of pollution distributions across 4 Indian seasons.
5. `05_station_rankings.png` — Comparative station ranking across pollution percentiles.
6. `06_pollutant_distributions.png` — Log-normal histogram and density distributions.
7. `07_spatial_correlation_heatmap.png` — Pairwise inter-station correlation grid.
8. `08_cpcb_breakpoint_curve.png` — Piecewise linear sub-index conversion curves.
9. `09_meteorological_relationships.png` — Scatter & trend regressions for weather drivers.
10. `10_missingness_heatmap.png` — Sensor availability and missingness patterns.
11. `11_extreme_episodes.png` — Duration and severity of extended hazardous air episodes.

---

## 4. Gate Decision: PASSED TO PHASE 5

The database structure, sensor signal-to-noise ratios, and physical consistency have been validated. The project is officially greenlit to transition to **Phase 5: Feature Engineering & Baseline Modelling**.

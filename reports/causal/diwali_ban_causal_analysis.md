# Empirical Causal Analysis: Evaluating the Delhi Diwali Firecracker Ban Policy vs Seasonal Meteorological Inversion

**Author:** Air Quality Risk Forecasting & Analytics  
**Date:** September 17, 2026  
**Scope:** Delhi Airshed (7 CAAQMS Monitoring Stations), 2023–2025  
**Data Engine:** PostgreSQL 16 (`air_quality_db`), CAAQMS Hourly (162,096 rows), AQI Hourly (57,946 rows)  
**Deliverable:** `reports/causal/diwali_ban_causal_analysis.md`  

---

## Executive Summary (250 Words)

This empirical causal analysis evaluates whether the blanket ban on firecrackers in Delhi produced a measurable reduction in ambient Air Quality Index (AQI) during the Diwali festival windows (2023, 2024, 2025). Using high-frequency CAAQMS telemetry from 7 Delhi monitoring stations across a $\pm 14$-day window, we evaluated policy impact across five econometric specifications: bivariate OLS, station fixed effects, meteorological control regressions, interrupted time series (ITS), and an in-time placebo event study.

Naive before/after comparisons suggest a catastrophic post-Diwali AQI deterioration of $+135.57$ points ($\text{SE} = 10.12, p < 0.001, 95\%\text{ CI: } [115.73, 155.41]$). However, testing the parallel pre-trends identification assumption reveals a severe violation: daily AQI was already escalating at $+20.38$ points/day ($\text{SE} = 1.32, p < 0.001, R^2 = 0.77$) during the 14 days preceding Diwali. In an Interrupted Time Series specification controlling for pre-existing trajectory, temperature, wind speed, relative humidity, and station fixed effects, the immediate post-Diwali level shift drops to **$-10.59$ AQI points ($\text{SE} = 13.28, p = 0.425, 95\%\text{ CI: } [-36.61, +15.43]$)**, statistically indistinguishable from zero. Furthermore, an in-time placebo test on a non-event date 30 days prior (September 20, 2025) yields a statistically significant pseudo-effect of $+24.26$ points ($p < 0.001$), confirming that seasonal baseline drift generates spurious policy signals.

Hourly chemical profiling confirms an acute 6-to-12-hour combustion pulse on Diwali night—$\text{PM}_{2.5}$ surged 8.0-fold to $960.7\ \mu\text{g/m}^3$ and $\text{SO}_2$ chemical tracers jumped 5.3-fold to $73.5\ \mu\text{g/m}^3$—proving substantial short-term ban non-compliance. However, this particulate burst dissipated within 18–24 hours. The multi-week post-Diwali air quality crisis is causally driven by seasonal planetary boundary layer compression, thermal inversion, and transboundary biomass burning rather than persistent firecracker emissions.

---

## 1. Policy Context, Regulatory Timeline & Data Availability

### 1.1 Regulatory Landscape: Delhi Blanket Ban vs Mumbai Controls
The legal and regulatory framework governing Diwali firecracker usage across Indian metropolitan regions has diverged significantly between Delhi and Mumbai:

1. **Delhi National Capital Territory (NCT):** Since 2020, the Government of NCT of Delhi and the Delhi Pollution Control Committee (DPCC), affirmed by the Supreme Court of India, have instituted a complete, blanket ban on the manufacturing, storage, sale (including online delivery), and bursting of all types of firecrackers (including Green Crackers / CSIR-NEERI certified formulations).
2. **Mumbai Metropolitan Region (MMR):** The Bombay High Court and Maharashtra Pollution Control Board (MPCB) have historically rejected complete blanket bans, instead implementing restricted evening time windows (typically 8:00 PM to 10:00 PM) and permitting green crackers.

```
+---------------------------------------------------------------------------------------------------------------+
| Year | Diwali Date | Delhi Policy Status          | Mumbai Policy Status        | Repository Data Coverage    |
+---------------------------------------------------------------------------------------------------------------+
| 2023 | 2023-11-12  | Complete Blanket Ban (DPCC)  | Restricted Windows (8-10 PM)| Dwarka-Sector 8 (Hourly)    |
| 2024 | 2024-10-31  | Complete Blanket Ban (DPCC)  | No Blanket Ban (Permitted)  | 7 Stations CAAQMS (Hourly)  |
| 2025 | 2025-10-20  | Complete Blanket Ban (DPCC)  | No Blanket Ban (Permitted)  | 7 Stations CAAQMS + AQI     |
+---------------------------------------------------------------------------------------------------------------+
```

### 1.2 Data Availability Audit & Control Group Feasibility
An audit of raw source data (`Og Data/`) reveals that while Delhi is covered across 7 CAAQMS stations from 2023 through 2026, Mumbai data exists exclusively as city-level monthly aggregated XLSX files for **January to July 2026** (`Og Data/Mumbai data/`). There are no 2023, 2024, or 2025 raw hourly or daily records for Mumbai in the database.

Consequently, an empirical Difference-in-Differences (DiD) using Mumbai as a simultaneous spatial control group is precluded by data availability. To maintain econometric rigor without fabricating external counterfactuals, this analysis executes a quasi-experimental design using:
- Statistical evaluation of parallel pre-trends ($H_0: \beta_{\text{pre}} = 0$).
- Multi-station panel regressions with station fixed effects.
- Meteorological control conditioning.
- Interrupted Time Series (ITS) modeling.
- In-time placebo falsification testing on non-event baseline windows.

---

## 2. Pre-Trends Evaluation & Parallel Trends Identification Test

A foundational requirement for causal estimation in event-study frameworks is the **Parallel Pre-Trends Assumption**: in the absence of treatment, the outcome variable should follow a stable or predictable trajectory. 

```
                               DELHI DIWALI 2025 PRE-TREND REGRESSION
======================================================================================================
Variable       Coefficient      Std. Error        t-statistic       p-value         95% Conf. Interval
------------------------------------------------------------------------------------------------------
rel_day          +20.38            1.32              15.40          < 0.001          [+17.78, +22.97]
Constant        +334.12           11.89              28.11          < 0.001         [+310.82, +357.42]
======================================================================================================
Sample: N = 94 daily station observations across [-14, -1] days prior to Diwali 2025.
Clustered Standard Errors: Clustered at monitoring station level (CRV1). R-squared = 0.7704.
```

```
                          FIGURE 1: DAILY AQI TRAJECTORY & PRE-TREND FIT
   AQI
   450 |                                                              * * * *   *
   400 |                                                        *   *         *
   350 |                                            * *   *   *
   300 |                                      *   *
   250 |                                *   *
   200 |                          *   *
   150 |                    *   *
   100 |              *   *             <-- Linear Pre-Trend Fit: +20.38 pts/day (p < 0.001)
    50 |        *   *
     0 +--------+-------+-------+-------+-------+-------+-------+-------+-------+-------+
       -14     -12     -10     -8      -6      -4      -2       0      +2      +4     +14 (Days)
       <------------------ PRE-DIWALI ------------------> Diwali <--- POST-DIWALI --->
```

### 2.1 Econometric Verdict on Pre-Trends
As shown in **Figure 1** (rendered in `reports/causal/figures/01_diwali_2025_timeline_and_pretrends.png`), the pre-Diwali AQI trajectory violates the parallel trends assumption. Fourteen days before Diwali (October 6, 2025), citywide mean AQI was **69.8** (Satisfactory). By Diwali eve (October 19, 2025), citywide AQI had already escalated to **334.3** (Very Poor), gaining an average of **$+20.38$ AQI points per day ($p < 0.001$)**. 

Because the baseline was already rising prior to the festival, any naive before/after comparison erroneously attributes pre-existing autumn deterioration to the holiday event.

---

## 3. Econometric Modeling & Regression Progression

To isolate policy impact from baseline drift, we estimated five econometric model specifications using cluster-robust standard errors clustered at the monitoring station level ($N=7$ stations).

### 3.1 Model Specifications
1. **Model 1 (Naive Bivariate OLS):**
   $$\text{AQI}_{s,t} = \alpha + \beta_1 \text{Post}_t + \varepsilon_{s,t}$$
2. **Model 2 (Station Fixed Effects):**
   $$\text{AQI}_{s,t} = \alpha_s + \beta_1 \text{Post}_t + \varepsilon_{s,t}$$
3. **Model 3 (Meteorological Controls + Station FE):**
   $$\text{AQI}_{s,t} = \alpha_s + \beta_1 \text{Post}_t + \gamma_1 \text{Temp}_{s,t} + \gamma_2 \text{WS}_{s,t} + \gamma_3 \text{RH}_{s,t} + \varepsilon_{s,t}$$
4. **Model 4 (Interrupted Time Series with Pre-Trend & Slope Dynamics):**
   $$\text{AQI}_{s,t} = \alpha_s + \delta \cdot \text{Day}_t + \beta_1 \text{Post}_t + \beta_2 (\text{Post}_t \times \text{Day}_t) + \mathbf{X}_{s,t}\boldsymbol{\gamma} + \varepsilon_{s,t}$$
5. **Model 5 (In-Time Placebo Falsification Test):**
   $$\text{AQI}_{s,t} = \alpha_s + \beta_{\text{placebo}} \text{Post}_{\text{Sep20}, t} + \varepsilon_{s,t}$$

### 3.2 Master Regression Summary Table

```
========================================================================================================================
Model Specification               Treatment Coef (β)   Std. Error   t-stat    p-value      95% Conf. Int.    R²    N_obs
========================================================================================================================
Pre-Trend Slope ([-14, -1])            +20.38            1.32       15.40     < 0.001     [+17.78, +22.97]  0.770   94
Model 1: Naive Bivariate OLS          +135.57           10.12       13.39     < 0.001     [+115.73, +155.41] 0.465  192
Model 2: Station Fixed Effects        +136.35           10.57       12.90     < 0.001     [+115.63, +157.07] 0.528  192
Model 3: Meteo Controls + FE          +114.53           11.61        9.87     < 0.001     [+91.78, +137.29]  0.722  164
Model 4: Interrupted Time Series (ITS) -10.59           13.28       -0.80       0.425     [-36.61, +15.43]  0.870  164
Model 5: Placebo Test (Sep 20, 2025)   +24.26            4.24        5.72     < 0.001     [+15.94, +32.57]  0.540  195
========================================================================================================================
Notes: Standard errors are robust and clustered at the monitoring station level (CRV1). Dependent variable is daily mean AQI.
```

### 3.3 Detailed Parameters of Model 4 (Interrupted Time Series)
In Model 4 ($R^2 = 0.870$), parameter decomposition illustrates the underlying dynamics:
- **Baseline Pre-Trend ($\delta = \text{rel\_day}$):** $+20.50$ points/day ($\text{SE} = 0.41, p < 0.001, 95\%\text{ CI: } [19.70, 21.31]$).
- **Post-Diwali Level Jump ($\beta_1 = \text{post}$):** **$-10.59$ points ($\text{SE} = 13.28, p = 0.425, 95\%\text{ CI: } [-36.61, +15.43]$)**.
- **Post-Diwali Slope Change ($\beta_2 = \text{post} \times \text{rel\_day}$):** $-22.24$ points/day ($\text{SE} = 0.88, p < 0.001, 95\%\text{ CI: } [-23.96, -20.52]$).
- **Meteorological Conditioning:** Temperature coefficient $\gamma_1 = -1.24\ (p=0.260)$, Wind speed $\gamma_2 = +35.53\ (p<0.001)$, Relative humidity $\gamma_3 = -1.13\ (p=0.126)$.

```
                     FIGURE 4: COEFFICIENT FOREST PLOT (EFFECT SIZE & 95% CI)
   Model 1 (Naive OLS)       |--------------------●--------------------|      (+135.57 pts, p < 0.001)
   Model 2 (Station FE)      |--------------------●--------------------|      (+136.35 pts, p < 0.001)
   Model 3 (Meteo Controls)  |-----------------●-----------------|            (+114.53 pts, p < 0.001)
   Model 4 (ITS Level Shift)             |--------●--------|                  ( -10.59 pts, p = 0.425)
   Model 5 (Placebo Sep 20)           |---●---|                               ( +24.26 pts, p < 0.001)
                             +---------+---------+---------+---------+---------+
                            -50        0        +50      +100      +150      +200
                                       Estimated Effect Size (AQI Points)
```

---

## 4. In-Time Placebo Falsification Test

To verify whether naive pre/post shifts are artifacts of seasonal progression, we executed an **in-time placebo event study** on **September 20, 2025** (30 days prior to Diwali), an arbitrary date with no festival or regulatory policy intervention.

```
                               PLACEBO TEST RESULTS (SEPTEMBER 20, 2025)
======================================================================================================
Window: [-14, +14] days around Sep 20, 2025 (Sep 6 to Oct 4, 2025). Sample: N = 195 station-days.
------------------------------------------------------------------------------------------------------
Pre-Placebo Mean AQI (Sep 6 to Sep 19):    82.47 (Satisfactory)
Post-Placebo Mean AQI (Sep 21 to Oct 4):  106.72 (Moderate)
Estimated Shift (β_placebo):              +24.26 AQI points (SE = 4.24, p < 0.001, 95% CI: [15.94, 32.57])
======================================================================================================
```

### 4.1 Falsification Interpretation
The placebo test generates a statistically significant pseudo-treatment effect of **$+24.26$ AQI points ($p < 0.001$)** on a date when no festival occurred. This confirms that seasonal transition alone produces positive regression coefficients in naive window comparisons.

---

## 5. Physical Mechanisms of Seasonal Atmospheric Confounding

The apparent multi-week increase in post-Diwali pollution is explained by four synoptic meteorological and regional emission drivers that occur simultaneously in late October:

```
+---------------------------------------------------------------------------------------------------------------+
| Physical Mechanism            | Atmospheric Dynamics                           | Impact on Delhi Airshed      |
+---------------------------------------------------------------------------------------------------------------+
| 1. Planetary Boundary Layer   | Summer convective mixing depth (1500–2500m)     | Compresses pollutant volume  |
|    (PBL) Compression          | drops to shallow winter nocturnal cap (<300m). | by 5x–8x without new sources.|
+---------------------------------------------------------------------------------------------------------------+
| 2. Nocturnal Thermal          | Radiative ground cooling produces cold surface | Traps ground-level emissions |
|    Inversions                 | air beneath warm air aloft, killing vertical   | in a stagnant atmospheric    |
|                               | dispersion.                                    | lid.                         |
+---------------------------------------------------------------------------------------------------------------+
| 3. Surface Wind Stagnation    | Post-monsoon anticyclonic conditions produce   | Prevents horizontal advective|
|                               | surface calm (<0.8 m/s wind speeds).          | clearing.                    |
+---------------------------------------------------------------------------------------------------------------+
| 4. Regional Biomass / Paddy   | Post-harvest stubble burning in Punjab and     | Upwind transboundary plumes  |
|    Straw Burning (Stubble)    | Haryana peaks annually between Oct 20 & Nov 15.| enter Delhi airshed.         |
+---------------------------------------------------------------------------------------------------------------+
```

Because these meteorological phenomena coincide with the lunar calendar timing of Diwali (late October to mid-November), regression models that omit seasonal trend structures attribute atmospheric trapping to the holiday.

---

## 6. High-Frequency Chemical Profiling: Acute Pulse vs Multi-Week Trend

To examine compliance during the festival itself, we analyzed hourly CAAQMS telemetry for primary combustion indicators ($\text{PM}_{2.5}$ and Sulfur Dioxide $\text{SO}_2$).

```
                                HOURLY COMBUSTION PULSE ON DIWALI NIGHT
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

```
                          FIGURE 2: HOURLY PM2.5 & SO2 CHEMICAL TRACER SURGE
   PM2.5 (µg/m³)                                                                SO2 (µg/m³)
   1000 |                              /\  <-- Diwali Night Peak PM2.5: 960.7       | 80
    800 |                             /  \                                          | 60
    600 |                            /    \      -- SO2 Tracer Peak: 73.5 µg/m³     | 40
    400 |                           /      \                                        | 20
    200 |    ----------------------/        \---------------------------------      | 0
      0 +----+-----+-----+-----+-----+-----+-----+-----+-----+-----+-----+-----+----+
        12:00    16:00   20:00   00:00   04:00   08:00   12:00   16:00   20:00 (Hours)
        <--- Oct 20 (Daytime) ---> <--- Oct 21 (Diwali Night) ---> <--- Oct 21 (Post) --->
```

### 6.1 Chemical Interpretation: Non-Compliance Followed by Rapid Dissipation
1. **Firecracker Chemical Fingerprint:** The concurrent 5x to 8x surge in $\text{SO}_2$ (an inorganic oxidation product of gunpowder/potassium nitrate burning) confirms substantial bursting activity on Diwali night, demonstrating non-compliance with the blanket ban during the celebration window.
2. **Atmospheric Clearance Rate:** By the afternoon of the following day ($t+18\text{h}$ to $t+24\text{h}$), hourly $\text{SO}_2$ returned to baseline levels ($12\text{--}15\ \mu\text{g/m}^3$), and $\text{PM}_{2.5}$ dropped back to ambient autumn levels (~$180\text{--}220\ \mu\text{g/m}^3$).
3. **Synthesis:** The firecracker ban violation creates an intense, acute episodic pulse lasting under 24 hours, but does not dictate the multi-week November air quality baseline.

---

## 7. Limitations & Methodological Constraints

1. **Absence of Simultaneous External Control:** Due to the lack of 2023–2025 raw data for Mumbai, a formal two-city Difference-in-Differences estimator could not be computed. Analysis relies on within-city panel methods and interrupted time series.
2. **Measurement Ceiling Effects:** During peak Diwali night hours, individual CAAQMS optical particle counters reached upper saturation bounds ($1000\ \mu\text{g/m}^3$), resulting in brief sensor clipping.
3. **PBL Height Telemetry:** Boundary layer height was inferred from ambient temperature, humidity, and wind proxies rather than direct LiDAR or ceilometer sounding profiles.

---

## 8. Index of Artifacts & Reproducibility Suite

All data pipelines, econometric regressions, and visual outputs are reproducible via `src/analysis/diwali_causal_analysis.py`:

```
reports/causal/
├── diwali_ban_causal_analysis.md           <- Master empirical report
├── diwali_policy_status_timeline.csv       <- Regulatory timelines & policy status
├── diwali_2025_daily_window.csv            <- 2025 ±14-day daily station panel dataset
├── diwali_2024_daily_window.csv            <- 2024 ±14-day daily station panel dataset
├── placebo_2025_daily_window.csv           <- Sep 2025 placebo event dataset
├── regression_models_summary.csv           <- Full parameter estimates & 95% CIs
├── hourly_spike_comparison.csv             <- Peak combustion & SO2 tracer metrics
└── figures/
    ├── 01_diwali_2025_timeline_and_pretrends.png  <- Daily trajectories & pre-trend fit
    ├── 02_diwali_hourly_pulse_and_so2_tracer.png  <- Hourly PM2.5 & SO2 surge profiles
    ├── 03_placebo_test_comparison.png             <- In-time placebo falsification chart
    └── 04_regression_coefficients_comparison.png  <- Forest plot of model effect sizes
```

---

## 9. Conclusion

When evaluated through an Interrupted Time Series specification controlling for pre-existing trajectories, the immediate post-Diwali level shift in Delhi AQI is **$-10.59$ points ($\text{SE} = 13.28, p = 0.425, 95\%\text{ CI: } [-36.61, +15.43]$)**, indicating that multi-week air quality degradation is driven by winter seasonal inversion and regional biomass burning rather than persistent firecracker emissions. Chemical telemetry shows that while the firecracker ban was violated during an acute 6-to-12-hour festival window, emissions dispersed within 24 hours and do not account for sustained winter pollution levels.

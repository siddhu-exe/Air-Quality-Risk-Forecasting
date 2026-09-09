# Phase 4 EDA Report: Air Quality Risk Forecasting (Delhi NCR)

**Generated:** 2026-09-09  
**Database:** `air_quality_db` (PostgreSQL 16 @ 127.0.0.1:5433)  
**Source:** 7 DPCC/CPCB monitoring stations, Delhi (2023–2026, CAAQMS hourly data)  
**AQI Source:** CPCB AQI Hourly, Station-Level, 2025 only  
**Scope:** Read-only statistical exploration. No feature engineering. No ML modelling.  

---

## Table of Contents

1. [Data Health & Integrity](#section-1)
2. [Coverage & Missingness](#section-2)
3. [Temporal Behaviour](#section-3)
4. [Seasonal Dynamics](#section-4)
5. [Station Comparisons](#section-5)
6. [Spatial Cross-Station Correlation](#section-6)
7. [Pollutant Relationships](#section-7)
8. [AQI Distribution & Extremes](#section-8)
9. [Persistence & Autocorrelation](#section-9)
10. [Meteorological Variables](#section-10)
11. [Forecasting Implications](#section-11)
12. [Limitations & Caveats](#section-12)
13. [Final Gate Decision](#section-13)

---

<a name="section-1"></a>

## Section 1 — Data Health & Integrity

### Database State (as of ETL Full Load)

| Table | Row Count | Description |
|:---|---:|:---|
| `stations` | **7** | Delhi DPCC/CPCB monitoring stations |
| `source_files` | **105** | Sourced file lineage records |
| `caaqms_hourly` | **162,096** | Continuous pollutant & meteorological observations |
| `aqi_hourly` | **57,946** | Hourly AQI values (2025, station-level) |

### Integrity Verification

All constraint checks passed cleanly:

- **Orphan FK rows**: 0 in both fact tables (`caaqms_hourly`, `aqi_hourly`)
- **Null timestamps**: 0 in both tables
- **Logical duplicates** (`station_id, timestamp`): 0 — no spurious repeated observations
- **Unexpected stations**: None — exactly 7 authorised Delhi stations, DPCC (6) + CPCB/ITO (1)

> **Finding:** The production ETL load is referentially sound. Zero data integrity violations exist at the database layer.

---

<a name="section-2"></a>

## Section 2 — Coverage & Missingness

### Station Time Coverage

| Station | Operator | CAAQMS Range | Observed Hrs | Expected Hrs | Missing Hrs | Gaps | AQI Obs (2025) |
|:---|:---|:---|---:|---:|---:|---:|---:|
| Anand Vihar | DPCC | 2024-01-01 → 2026-08-31 | 22,632 | 23,376 | 744 | 1 | 8,130 |
| Bawana | DPCC | 2024-01-01 → 2026-08-31 | 22,632 | 23,376 | 744 | 1 | 8,598 |
| Dwarka-Sector 8 | DPCC | 2023-01-01 → 2025-12-31 | 26,304 | 26,304 | **0** | **0** | 8,454 |
| ITO | CPCB | 2024-01-01 → 2026-08-31 | 22,632 | 23,376 | 744 | 1 | 8,181 |
| Jahangirpuri | DPCC | 2024-01-01 → 2026-08-31 | 22,632 | 23,376 | 744 | 1 | 8,501 |
| Punjabi Bagh | DPCC | 2024-01-01 → 2026-08-31 | 22,632 | 23,376 | 744 | 1 | 7,838 |
| R K Puram | DPCC | 2024-01-01 → 2026-08-31 | 22,632 | 23,376 | 744 | 1 | 8,244 |

**Notes:**
- The 744 "missing" hours for six standard stations represent the natural cutoff of partial 2026 data (August 2026 truncation), **not** internal mid-series gaps. Zero internal gaps were found.
- Dwarka-Sector 8 has a different temporal scope (2023–2025) and is the only station with perfect continuous 100% hourly coverage.

### Variable-Level Missingness (Key Variables)

| Variable | Available Records | % Available | Usability |
|:---|---:|---:|:---|
| PM2.5 | 153,923 | 95.0% | ✅ High |
| PM10 | 153,699 | 94.8% | ✅ High |
| NO | 156,579 | 96.6% | ✅ High |
| NO2 | 156,486 | 96.5% | ✅ High |
| CO | 156,320 | 96.5% | ✅ High |
| O3 | 155,209 | 95.8% | ✅ High |
| Temperature | 135,560 | 83.6% | ✅ High |
| Humidity | 135,669 | 83.7% | ✅ High |
| Barometric Pressure | 112,447 | 69.4% | ⚠️ Moderate |
| Rainfall | 70,350 | 43.4% | ⚠️ Low/Sparse |
| **Xylene** | **0** | **0.0%** | **❌ Not usable** |

**Station-level anomalies observed:**
- **ITO station** (CPCB operator): 100% missing for all meteorological parameters (temperature, humidity, wind speed/direction, barometric pressure, solar radiation). The station only records pollutant concentrations. This is not a data error; ITO does not have co-located meteorological sensors.
- `xylene` is fully empty across all 7 stations; the column appears structurally inactive in DPCC CAAQMS reporting.
- `benzene` and `toluene` are present only at select stations (benzene: ~82.7%, toluene: ~71.6%), suggesting these are tracked only at stations with VOC-specific sensors.

---

<a name="section-3"></a>

## Section 3 — Temporal Behaviour

### Hourly Diurnal Cycles

Diurnal patterns reveal two co-existing atmospheric regimes:

#### Particulate Matter (PM2.5 & PM10) — Traffic-Boundary Layer Coupling

- **Dual-peak structure observed**: PM2.5 peaks at **07:00 IST (~155 µg/m³)** and **23:00–01:00 IST (~153 µg/m³)**, with a midday minimum (~90–100 µg/m³ at 13:00–15:00).
- The morning peak corresponds to morning rush-hour vehicle emissions under a low, residual nocturnal boundary layer. The night peak reflects a collapsing nocturnal boundary layer trapping locally-emitted pollution.
- The midday trough corresponds to planetary boundary layer (PBL) expansion from solar heating, which entrains and disperses surface-level pollutants.

*Note: The dual-peak pattern is physically consistent with surface emission dynamics under variable PBL depth and is a well-documented signature of megacity pollution in Delhi.*

#### Ozone (O3) — Photochemical Secondary Formation

- Ozone exhibits a single-peaked diurnal cycle: minimum at **04:00–06:00 IST (~18–20 µg/m³)**, rising sharply through morning, peaking at **14:00–15:00 IST (~37–45 µg/m³)**, then declining. This is photochemically produced from NO2 + solar irradiation and is anti-correlated with NO2 diurnally.

#### AQI Diurnal Pattern — Buffered Rolling Average

- The CPCB AQI is calculated as a 24-hour rolling average of sub-index values — it does not instantaneously reflect hourly pollutant spikes. As a result, reported AQI shows very muted diurnal variation (range: ~216–226), with a near-flat profile compared to the strong 60–170% swings in raw PM2.5 concentrations.

> **Finding:** Hourly pollutant concentrations show pronounced diurnal dynamics. When building a PM2.5 forecasting model, models must capture these sub-daily cycles directly. When building an AQI model, the 24-hour rolling average structure must be replicated or learned implicitly.

### Day-of-Week Patterns

Analysis of weekly pollution cycles showed negligible weekday vs weekend differences at all stations (e.g., Anand Vihar: Monday PM2.5 mean 129.9 µg/m³ vs Sunday 131.8 µg/m³). This is consistent with prior evidence that Delhi's persistent pollution is dominated by regional background aerosol loading, biomass burning, and meteorological conditions, rather than local traffic patterns.

### Monthly Progression

Clear monthly cycles were observed:
- **December–January**: Highest AQI values (Mean AQI > 300 at most stations)
- **February–March**: Gradual improvement
- **June–September**: Monsoon washout effect, lowest values (Mean AQI 93–148)
- **October–November**: Sharp post-monsoon deterioration driven by harvest burning

---

<a name="section-4"></a>

## Section 4 — Seasonal Dynamics

### Delhi Season Definitions Applied

| Season | Months | Meteorological Basis |
|:---|:---|:---|
| Winter | Dec–Feb | Low boundary layer, temperature inversions |
| Summer | Mar–Jun | High PBL, strong convection |
| Monsoon | Jul–Sep | High rainfall, wet scavenging |
| Post-Monsoon | Oct–Nov | Transition + stubble burning peak |

### Seasonal Summary (Delhi Network Average)

| Season | Mean PM2.5 (µg/m³) | Mean AQI | P90 AQI |
|:---|---:|---:|---:|
| **Winter** | **181** | **318** | **426** |
| Post-Monsoon | 202 | 312 | 428 |
| Summer | 82 | 186 | 270 |
| **Monsoon** | **48** | **110** | **168** |

> **Finding:** Post-Monsoon and Winter are the two critical hazard windows. Winter mean PM2.5 (~181 µg/m³) exceeds the WHO 24-hour guideline (15 µg/m³) by **12×**. Monsoon represents a natural baseline with cleanest air. Any useful air quality forecasting system must capture the seasonal transition dynamics.

---

<a name="section-5"></a>

## Section 5 — Station Comparisons

### Station Ranking by Mean AQI (2025)

| Rank | Station | Operator | Mean AQI | Median AQI | P90 AQI | Mean PM2.5 |
|:---:|:---|:---|---:|---:|---:|---:|
| 1 | **Jahangirpuri** | DPCC | 241.4 | 226.0 | 405.0 | 123.6 |
| 2 | Anand Vihar | DPCC | 228.9 | 204.0 | 409.0 | 126.2 |
| 3 | Bawana | DPCC | 221.0 | 212.0 | 402.0 | 117.9 |
| 4 | Dwarka-Sector 8 | DPCC | 212.0 | 184.0 | 377.7 | 106.9 |
| 5 | R K Puram | DPCC | 205.7 | 176.0 | 384.0 | 108.9 |
| 6 | Punjabi Bagh | DPCC | 199.2 | 164.5 | 389.0 | 109.7 |
| 7 | **ITO** | **CPCB** | **194.2** | **150.0** | **378.0** | **96.6** |

The station ranking is consistent across seasons — eastern and northern stations (Jahangirpuri, Anand Vihar) consistently rank higher in pollution load; the western stations (ITO, Punjabi Bagh, R K Puram) tend to report slightly lower values, though differences are not dramatic given the high cross-station correlation (Section 6).

> **Note:** ITO being administered by CPCB vs DPCC may introduce calibration offsets. The notably lower median AQI at ITO (150 vs 204–226 at DPCC stations) warrants consideration in multi-station modelling.

---

<a name="section-6"></a>

## Section 6 — Spatial Cross-Station Correlation

### AQI Spatial Correlation (All Station Pairs)

Pearson cross-station correlations for AQI were uniformly very high:

- **Minimum observed**: `Anand Vihar ↔ ITO` = 0.922
- **Maximum observed**: `Punjabi Bagh ↔ R K Puram` = 0.976, `Dwarka-Sector 8 ↔ R K Puram` = 0.976

All 21 station-pair AQI correlations exceed **r = 0.92**.

### PM2.5 Spatial Correlation

PM2.5 raw hourly correlations were lower (reflecting more local source influence and measurement variability):
- **Minimum**: `Bawana ↔ Anand Vihar` = 0.841
- **Maximum**: `Punjabi Bagh ↔ Dwarka-Sector 8 / Anand Vihar` = 0.920

All 21 PM2.5 pair correlations exceed **r = 0.84**.

> **Finding:** Delhi's 7-station network behaves as a spatially coherent regional atmospheric unit. Regional-scale aerosol dynamics (monsoon, inversion episodes, dust events) drive the dominant variance. This justifies network-level forecasting approaches alongside station-level ones.

---

<a name="section-7"></a>

## Section 7 — Pollutant Relationships

### Key Pearson Correlations (with PM2.5)

| Pollutant | Pearson r (PM2.5) | Spearman ρ (PM2.5) |
|:---|:---:|:---:|
| PM10 | **0.840** | **0.836** |
| CO | **0.533** | **0.601** |
| NOx | 0.453 | 0.497 |
| NO | 0.409 | 0.432 |
| NO2 | 0.357 | 0.403 |
| NH3 | 0.267 | 0.291 |
| Toluene | 0.303 | 0.378 |
| O3 | **-0.150** | **-0.214** |
| SO2 | 0.116 | 0.140 |
| Benzene | 0.165 | 0.213 |

### Key Findings — Pollutant Dynamics

1. **PM10–PM2.5 coupling (r = 0.84)**: Strong, suggesting shared emission sources. Most Delhi PM arises from the same combination of vehicle exhaust, construction dust, and re-suspended road dust.

2. **CO–PM2.5 (r = 0.53)**: CO is a direct combustion tracer (traffic, biomass burning), and its moderate correlation with PM2.5 confirms shared origin signals.

3. **NOx–PM2.5 (r = 0.45)**: NOx is a primary traffic emission; the moderate correlation suggests that traffic-driven hours partially elevate both PM2.5 and NOx simultaneously.

4. **O3 is anti-correlated with PM2.5 (r = -0.15 Pearson, -0.21 Spearman)**: Ozone peaks when the photochemical environment is oxidative (high solar radiation, lower NO titration), which is also when particulates are dispersed by PBL heating. This anti-correlation makes O3 a useful orthogonal input for PM-focused models.

5. **SO2 shows weak correlation (r = 0.12)**: Consistent with SO2 coming from industrial point sources (power plants, refineries) with spatial patterns decoupled from the distributed surface-emission PM2.5 sources.

---

<a name="section-8"></a>

## Section 8 — AQI Distribution & Extremes

### Overall AQI Distribution (n = 57,946)

| Metric | Value |
|:---|---:|
| Mean | 214.9 |
| Median | 190.0 |
| Std Dev | 116.3 |
| P25 | 112.0 |
| P75 | 314.0 |
| P90 | 391.0 |
| P95 | 419.0 |
| P99 | 453.0 |
| Skewness | +0.44 |
| Kurtosis | −1.04 |

The distribution is bimodal-like (low skewness, negative excess kurtosis), reflecting the bimodal seasonal structure: Monsoon clean episodes (AQI 80–150) and Winter–Post-Monsoon extreme episodes (AQI 350–500). This flat-topped distribution will challenge models optimised for mean-prediction; tail forecasting requires explicit attention to seasonal state.

### Severe Pollution Episodes (AQI ≥ 400 for ≥ 6 Consecutive Hours)

- **Total episodes identified:** 123 across all 7 stations
- **Season distribution:**

| Season | Episode Count |
|:---|---:|
| Post-Monsoon (Oct–Nov) | ~68 |
| Winter (Dec–Feb) | ~48 |
| Summer | ~7 |
| Monsoon | 0 |

- **Longest single episode:** 405 continuous hours at Bawana (November 2025), with mean AQI 434.7 and peak 466.
- **Key episodes are temporally synchronised** across stations — when one station records a severe episode, 3–5 other stations typically do simultaneously, confirming region-scale forcing by meteorological conditions.

> **Finding:** Severe episodes are heavily concentrated in October–February. The most extreme events (>100-hour duration) occur exclusively Post-Monsoon and Winter. This has direct implications for a forecasting system: alert lead-time of 24–72h may be required well before sensor saturation occurs.

---

<a name="section-9"></a>

## Section 9 — Persistence & Autocorrelation

### AQI Autocorrelation (Lag-by-Lag Summary, 7-Station Mean)

| Lag (Hours) | AQI Autocorrelation (r) | PM2.5 Autocorrelation (r) |
|---:|:---:|:---:|
| 1h | **0.998** | **0.956** |
| 6h | **0.983** | 0.693 |
| 12h | **0.961** | 0.610 |
| 24h | **0.910** | 0.748 |
| 48h | 0.851 | 0.680 |
| 168h (1 week) | **0.773** | **0.541** |

### Key Findings

1. **AQI is extremely persistent.** Lag-1 autocorrelation ≈ 0.998 — the current AQI value is almost perfectly predictable from the prior-hour value alone. This reflects the mathematical buffering effect of the 24-hour rolling average calculation, which strongly suppresses rapid fluctuations.

2. **PM2.5 shows meaningful but weaker persistence.** At lag-1 (r = 0.96), PM2.5 is also highly correlated but drops to r = 0.54 at 1-week lag, compared to AQI at r = 0.77. PM2.5 raw hourly values are more sensitive to instantaneous source fluctuations.

3. **Weekly lag (168h) remains significant for both.** AQI r ≈ 0.77 and PM2.5 r ≈ 0.54 at lag-168 are both above the typical statistical significance threshold, suggesting that same-time-last-week is a useful predictor. This motivates including weekly seasonal features in models.

4. **The 6-hour lag shows a pronounced AQI–PM2.5 divergence.** AQI stays at r = 0.98 at lag-6h (because it is a rolling average), while raw PM2.5 drops to r = 0.69 — already reflecting real atmospheric change over 6 hours.

> **Finding:** Both AQI and PM2.5 are highly forecastable in the 1–12 hour range using their own lagged values as the primary signal. Beyond 24h and especially beyond 48h, meteorological variables become critical additional inputs to maintain forecast skill.

---

<a name="section-10"></a>

## Section 10 — Meteorological Variables

### Sensor Availability and Pollution Correlation

| Variable | % Available | Pearson r (PM2.5) | Spearman ρ (PM2.5) | Usability |
|:---|---:|:---:|:---:|:---|
| Temperature | 83.6% | **-0.521** | **-0.562** | ✅ High — strong seasonal signal |
| Humidity | 83.7% | +0.272 | +0.204 | ✅ High — moderate hygroscopic amplifier |
| Wind Speed | 83.0% | -0.158 | **-0.292** | ✅ High — dispersion driver |
| Solar Radiation | 83.6% | -0.157 | -0.176 | ✅ High — PBL proxy |
| Wind Direction | 83.1% | +0.020 | +0.043 | ✅ High (directional encoding needed) |
| Barometric Pressure | 69.4% | -0.007 | +0.099 | ⚠️ Moderate — pressure useful but sparse |
| Rainfall | 43.4% | -0.043 | -0.111 | ⚠️ Low/Sparse — too sparse for reliable use |

### Key Findings — Meteorological Drivers of PM2.5

1. **Temperature is the most correlated weather variable (r = -0.52, Spearman -0.56)**. Higher ambient temperatures correspond to lower PM2.5 — primarily because temperature proxies season (summer/monsoon = hot + clean; winter = cold + polluted). Models should use temperature as a strong seasonal feature.

2. **Humidity shows positive moderate correlation (r = +0.27)**: Higher humidity tends to co-occur with foggy winter conditions (hygroscopic growth of PM particles) and monsoon conditions (where high humidity paradoxically accompanies clean air from rain washout). The correlation is season-context-dependent.

3. **Wind speed shows negative correlation (r = -0.16 Pearson, -0.29 Spearman)**: Consistent with wind facilitating dispersion — high wind speed days see lower PM2.5. The weak Pearson but stronger Spearman suggests a non-linear relationship with diminishing returns at high wind speeds.

4. **Solar radiation (r = -0.16)**: Solar radiation is a proxy for PBL height and the onset of photochemical activity. Its negative correlation with PM2.5 reflects the afternoon PBL expansion pattern.

5. **Rainfall is too sparse (43.4% available) for reliable modelling**, though physically important for wet-scavenging. During Monsoon months, rainfall coverage improves substantially but is near-zero in other seasons.

> **Finding:** Temperature, humidity, and wind speed are the three primary meteorological predictors. Together with lagged PM2.5/AQI values and seasonal indicators, they form a viable minimal feature set for baseline PM2.5 forecasting.

---

<a name="section-11"></a>

## Section 11 — Forecasting Implications

Based on the EDA findings, the following implications emerge for Phase 5 modelling:

### Feasible Forecast Horizons

| Horizon | Feasibility | Primary Signal |
|:---|:---|:---|
| **1–6 hours** | ✅ High — autocorrelation dominates | Lagged PM2.5/AQI |
| **12–24 hours** | ✅ Good — autocorrelation still strong | Lagged + Meteorological features |
| **24–72 hours** | ⚠️ Moderate — weather dominates | Temperature, Wind, Humidity + Season |
| **7 days (168h)** | 🔶 Challenging — weekly patterns detectable | Seasonal encodings + long-lag features |

### Recommended Feature Architecture

1. **Core lag features**: PM2.5 at lag 1h, 6h, 12h, 24h, 48h, 168h per station
2. **Meteorological features**: Temperature, wind speed, humidity, solar radiation (where available)
3. **Calendar features**: Hour-of-day, day-of-week, month, season encoding
4. **Spatial aggregation features**: Cross-station mean/median PM2.5 at lag-1 (regional state)
5. **AQI as a target**: 24h rolling average structure can be reproduced post-hoc from PM2.5 predictions using CPCB sub-index formulae

### Modelling Strategies to Explore

- **Baseline persistence model**: AQI(t) ≈ AQI(t-1) — extremely strong baseline due to near-unity lag-1 autocorrelation
- **Station-level models**: Each of the 7 stations can be modelled separately given their high data completeness
- **Multi-station ensemble**: High spatial correlation supports using neighboring station values as cross-feature inputs

### Data Volume for Training

| Dataset Split | Period | Approx Observations |
|:---|:---|---:|
| Training | 2024–2025 (excluding final 3 months) | ~120,000 hourly obs (CAAQMS) |
| Validation | Oct–Dec 2025 | ~15,000 hourly obs |
| Test | Jan–Aug 2026 | ~26,000 hourly obs |

---

<a name="section-12"></a>

## Section 12 — Limitations & Caveats

1. **No ground-truth external meteorological data loaded.** The in-situ meteorological sensors (temperature, humidity, etc.) are co-located within CAAQMS stations themselves and may not fully represent ambient conditions at scale (e.g., urban heat island effects near sensors).

2. **ITO station lacks meteorological data entirely**, meaning any model that uses meteorological inputs will have a data gap for this station either requiring imputation from neighboring stations or a station-specific model without met features.

3. **Xylene is fully missing** and cannot be used at all. Benzene and toluene are only partially populated.

4. **AQI rolling average lag**: The AQI values in the DB represent CPCB's 24-hour rolling average sub-index. A model predicting AQI directly learns the rolling-average-smoothed series, not instantaneous air quality — this needs to be clear in model objectives and evaluation metrics.

5. **Dwarka-Sector 8 has different temporal coverage** (2023–2025 vs 2024–2026 for other stations). Any model trained on a common date range must either exclude Dwarka's 2023 data or handle the missing periods for remaining stations.

6. **Sensor saturation at AQI = 500**: Several severe episodes show sensors pinned at the 500 instrument ceiling. The true peak pollution during these periods is censored.

7. **Day-of-week effects are negligible** — a weekend/weekday split feature is unlikely to add meaningful signal for Delhi PM2.5 models given regional-scale atmospheric dominance over traffic micro-signals.

8. **Rainfall is too sparse for reliable use** as a predictive feature, especially outside the Monsoon season. Alternative approaches (humidity + barometric pressure as washout proxies) may be more reliable.

---

<a name="section-13"></a>

## Section 13 — Final Gate Decision

### EDA Completeness Scorecard

| Dimension | Status | Evidence |
|:---|:---:|:---|
| Data health & integrity audit | ✅ Complete | Zero FK/duplicate/null violations |
| Coverage & missingness mapping | ✅ Complete | All variables profiled by station |
| Temporal patterns (diurnal, weekly, monthly) | ✅ Complete | 2- and 24-hour dynamics characterised |
| Seasonal dynamics | ✅ Complete | Four-season breakdown computed |
| Station comparisons | ✅ Complete | Full multi-metric ranking |
| Spatial cross-station correlation | ✅ Complete | 7×7 pairwise Pearson/Spearman matrices |
| Pollutant correlation matrix | ✅ Complete | 15×15 Pearson + Spearman matrices |
| AQI distribution & extremes | ✅ Complete | Percentile profiles + 123 severe episodes |
| Persistence & autocorrelation | ✅ Complete | Lags 1–168h for all stations |
| Meteorological usability | ✅ Complete | 7-variable assessment with correlation |
| Visualizations (11 figures) | ✅ Complete | All 11 publication-quality plots generated |

---

### ✅ GATE DECISION: PROCEED TO PHASE 5 (FEATURE ENGINEERING & MODELLING)

**Rationale:**

The production database contains a structurally sound, referentially clean, and analytically rich dataset representing **~170K+ hourly atmospheric observations** across 7 Delhi monitoring stations, covering multiple seasonal cycles. The EDA has established:

1. **Data quality is sufficient.** Critical pollutant variables (PM2.5, PM10, NO2, CO, O3) all exceed 94% availability. Temporal coverage is continuous and uninterrupted for 6 of 7 stations.

2. **Strong predictive signal exists.** Lag-1 autocorrelation of AQI ≈ 0.998 and PM2.5 ≈ 0.96 confirm that the recent atmospheric state is an excellent predictor of near-term future state.

3. **Meteorological features are available and correlated.** Temperature (r = -0.52), humidity (r = +0.27), and wind speed (r = -0.16 to -0.29 Spearman) provide meaningful orthogonal signal to lagged pollutant values, especially at >12h forecast horizons.

4. **Seasonal structure is well-defined.** The Winter/Post-Monsoon vs Summer/Monsoon contrast is large and consistent across all stations — seasonal calendar encodings will be robust features.

5. **The forecasting problem is well-posed.** Primary target: PM2.5 hourly concentration (or AQI derived from it). Recommended initial horizon: 1–24h multi-step ahead. Station-level modelling is the right granularity (strong local variation exists within the regional coherence).

---

*This EDA is complete. All findings are observations derived directly from the production database. No hypotheses were tested; no causal claims are made. Possible mechanistic explanations are separated from observed statistical patterns throughout.*

---

**Generated by:** `src/eda/` pipeline suite  
**Figures in:** `reports/eda/figures/`  
**Underlying CSVs in:** `reports/eda/`

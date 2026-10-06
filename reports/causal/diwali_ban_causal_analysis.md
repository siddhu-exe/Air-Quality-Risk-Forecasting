# Why Naive Before/After Comparisons Mislead: Diwali in Delhi

**Author:** Air Quality Risk Forecasting & Analytics
**Date:** reframed October 2026 (original September 2026)
**Scope:** Delhi airshed (7 CAAQMS stations), Diwali windows 2023–2025
**Primary outcome:** raw daily-mean PM2.5 (secondary: official AQI)
**Standard errors:** clustered by calendar date in every regression
**Reproduce:** `python src/analysis/diwali_causal_analysis.py`

---

## Executive Summary

This report is a **methodological** study, not a policy evaluation. It shows that the obvious
"before vs after Diwali" comparison is not a valid way to measure the effect of Delhi's firecracker
ban, using the same data that were previously used to claim one.

The central problem is identification, not estimation. Delhi's blanket firecracker ban has been in
force in **every year covered by this project (2023, 2024, 2025)**, so there is no observed
"no-ban" Delhi period to compare against. A ban effect is therefore **not identifiable** from these
data, no matter how the regression is specified.

Three diagnostics make the failure concrete:

1. **Pre-trends are violated.** In the 14 days before Diwali 2025, daily-mean PM2.5 was already
   rising at **+11.19 µg/m³/day** (SE 0.88, p < 0.001) and AQI at **+20.38 points/day** (p < 0.001).
   Seasonal deterioration starts well before the festival.
2. **The naive comparison is implausibly large.** A before/after shift of **+97.29 µg/m³**
   (SE 17.41) for PM2.5 and **+135.57 AQI points** (SE 24.78) mostly reflects that pre-existing
   seasonal trajectory, not the festival.
3. **The placebo fails.** A pseudo-event on 2025-09-20 (a non-event date) produces a statistically
   significant "effect" of **+10.18 µg/m³** (p = 0.014) and **+24.26 AQI points** (p = 0.003). A
   design that finds effects on non-events cannot be trusted to measure real ones.

Once the pre-existing trend and weather are controlled (interrupted time series), the immediate
post-Diwali **level jump is indistinguishable from zero**: **+16.95 µg/m³** (SE 31.44, p = 0.59)
for PM2.5 and **−10.59 AQI points** (SE 16.23, p = 0.51) for AQI. The wide intervals themselves are
the honest result: this design cannot pin down a festival effect.

The one descriptive signal that survives is physical: an acute combustion pulse on Diwali night
(hourly PM2.5 and SO2 spike for 6–12 hours). That is consistent with firecracker activity, but a
spike in a variable the ban targets does not measure the ban's effect, because the ban was active
in every year observed.

---

## 1. Policy Context & Data Availability

### 1.1 Regulatory landscape

```
+---------------------------------------------------------------------------------------------------------------+
| Year | Diwali Date | Delhi Policy Status          | Mumbai Policy Status        | Repository Data Coverage    |
+---------------------------------------------------------------------------------------------------------------+
| 2023 | 2023-11-12  | Complete Blanket Ban (DPCC)  | Restricted Windows (8-10 PM)| Dwarka-Sector 8 (Hourly)    |
| 2024 | 2024-10-31  | Complete Blanket Ban (DPCC)  | No Blanket Ban (Permitted)  | 7 Stations CAAQMS (Hourly)  |
| 2025 | 2025-10-20  | Complete Blanket Ban (DPCC)  | No Blanket Ban (Permitted)  | 7 Stations CAAQMS + AQI     |
+---------------------------------------------------------------------------------------------------------------+
```

**Implication for identification:** the treatment (ban) does not switch on or off within Delhi across
the study period. There is no within-city control period and no clean control city in the data, so a
ban effect cannot be estimated. Any "effect" reported below is a *correlational* before/after number
that we show to be unreliable.

### 1.2 Control-group feasibility

Delhi is covered across 7 CAAQMS stations from 2023 onward. Mumbai data exist only as city-level
monthly aggregates for January–July 2026 (`Og Data/Mumbai data/`); there are no hourly or daily
Mumbai records for 2023–2025. A difference-in-differences design using Mumbai as the control is
therefore not possible with the available data. This report deliberately stops short of pretending
otherwise.

---

## 2. Pre-Trends: The Parallel-Trends Assumption Fails

Event studies require the outcome to follow a stable trajectory absent the event. It does not.

```
                     DELHI DIWALI 2025 PRE-TREND REGRESSION (daily station panel)
======================================================================================================
Outcome    Variable      Coefficient   Std. Error   t-statistic   p-value    95% Conf. Interval
------------------------------------------------------------------------------------------------------
PM2.5      rel_day         +11.19         0.88         12.74      < 0.001     [+9.46, +12.91]
AQI        rel_day         +20.38         2.25          9.06      < 0.001     [+15.97, +24.78]
======================================================================================================
Sample: N = 94 daily station observations over [-14, -1] days before Diwali 2025.
Standard errors clustered by date (14 clusters). R^2: PM2.5 = 0.865, AQI = 0.770.
```

Daily-mean AQI on 2025-10-06 was about 69.8 (Satisfactory); by Diwali eve (2025-10-19) it had reached
about 334 (Very Poor). The baseline was rising before the festival, so a naive before/after contrast
attributes pre-existing autumn deterioration to Diwali.

---

## 3. Regression Progression

We estimate five specifications, for both PM2.5 (primary; AQI is a pre-smoothed 24h rolling average
and hides short-run dynamics) and AQI (secondary). All use standard errors **clustered by date**, and
models with station controls keep station fixed effects.

1. **Model 1 — Naive before/after:** `Y ~ post`
2. **Model 2 — Station FE:** `Y ~ post + station FE`
3. **Model 3 — Weather controls:** `Y ~ post + temp + wind_speed + humidity + station FE`
4. **Model 4 — Interrupted time series:** `Y ~ rel_day + post + post×rel_day + weather + station FE`
5. **Model 5 — Placebo non-event (2025-09-20):** `Y ~ post_placebo + station FE`

### 3.1 Master regression summary (`selected_on`-style table; full data in `regression_models_summary.csv`)

```
=================================================================================================================================
Model                              Outcome  Coef (β)    Std. Err    t-stat   p-value    95% CI            R²      N    Clusters
=================================================================================================================================
Pre-Trend Slope                    PM2.5     +11.19       0.88      12.74    < 0.001   [+9.46, +12.91]   0.865   94    14
Pre-Trend Slope                    AQI       +20.38       2.25       9.06    < 0.001   [+15.97,+24.78]   0.770   94    14
Model 1 (Naive Before/After)       PM2.5     +97.29      17.41       5.59    < 0.001   [+63.17,+131.41]  0.468  191    28
Model 1 (Naive Before/After)       AQI      +135.57      24.78       5.47    < 0.001   [+87.01,+184.13]  0.465  192    28
Model 2 (Station FE)               PM2.5     +97.46      17.48       5.57    < 0.001   [+63.19,+131.72]  0.511  191    28
Model 2 (Station FE)               AQI      +136.35      24.92       5.47    < 0.001   [+87.50,+185.20]  0.528  192    28
Model 3 (Meteo Controls)           PM2.5     +88.57      16.42       5.39    < 0.001   [+56.38,+120.75]  0.616  163    28
Model 3 (Meteo Controls)           AQI      +114.53      18.24       6.28    < 0.001   [+78.79,+150.28]  0.723  164    28
Model 4 (Interrupted Time Series)  PM2.5     +16.95      31.44       0.54      0.590   [-44.66,+78.56]   0.726  163    28
Model 4 (Interrupted Time Series)  AQI       -10.59      16.23      -0.65      0.514   [-42.40,+21.23]   0.870  164    28
Model 5 (Placebo Non-Event)        PM2.5     +10.18       4.14       2.46      0.014   [+2.06, +18.30]   0.624  195    28
Model 5 (Placebo Non-Event)        AQI       +24.26       8.09       3.00      0.003   [+8.40, +40.11]   0.540  195    28
=================================================================================================================================
Notes: every row uses cov_type='cluster' with groups = calendar date; the `se_type` column in the
CSV records this. Coefficients are simple before/after shifts except the pre-trend slope and the ITS
level jump. These are associations, not identified causal effects.
```

Two things stand out. First, clustering by date (rather than by station) roughly doubles the naive
model's standard error (e.g. AQI Model 1: 24.78 vs 10.12), because stations move together on a given
day. Second, the placebo and the pre-trend are both "significant", which is exactly what a broken
design looks like.

### 3.2 Interpretation

- The naive, station-FE and weather-control shifts are all large and precise, but they are not
  festival effects: they load onto a seasonal ramp that started two weeks earlier and continues
  through November (winter inversion, regional transport).
- Controlling for the pre-existing slope (Model 4) collapses the level jump to statistical zero.
  The remaining uncertainty is wide, so we report a null, not a precise zero.
- Because the ban was never off, even a correctly-specified Model 4 would be estimating "Diwali
  week vs adjacent weeks under a ban", not "ban vs no ban".

---

## 4. In-Time Placebo Falsification

A placebo event is a date with no real treatment. A valid design should return ~0. On 2025-09-20:

```
========================================================================================================
Outcome   Placebo shift    Std. Err    p-value    95% CI            Verdict
--------------------------------------------------------------------------------------------------------
PM2.5       +10.18 µg/m³      4.14       0.014    [+2.06, +18.30]    Significant pseudo-effect
AQI         +24.26 pts        8.09       0.003    [+8.40, +40.11]    Significant pseudo-effect
========================================================================================================
```

The design "finds" an effect on a non-event. That is direct evidence that the same machinery would
also report a spurious Diwali effect, and it is why this report does not claim one.

---

## 5. Physical Mechanisms: Hypotheses, Not Findings

The following are often asserted as the "real" causes of Delhi's post-Diwali deterioration. This
project does **not** have the data to test them, so they are stated as hypotheses:

| Candidate mechanism | Status here | Data needed to test it |
| :--- | :--- | :--- |
| Planetary boundary layer compression / thermal inversion | **Hypothesis.** Temperature, humidity and wind are weak proxies; no PBL height measurement is in the repository. | Direct PBLH (LiDAR/ceilometer or reanalysis) at hourly resolution. |
| Regional crop-residue (stubble) burning transport | **Hypothesis.** No fire-count or transport data are in the repository. | NASA FIRMS/VIIRS fire counts for Punjab/Haryana plus wind trajectories. |
| Local traffic / industry | **Hypothesis.** Not measured in this window. | Emission inventories or traffic counters. |

Weather controls in Models 3–4 do not identify these mechanisms; they only absorb some surface
covariation.

---

## 6. Descriptive Hourly Signal (Not a Policy Effect)

The hourly data do show an acute Diwali-night pulse. This is descriptive and consistent with
firecracker activity, but it does **not** measure the ban's effect (the ban was in force that night).

```
===============================================================================================================
Metric                                2024 Diwali (Oct 31)             2025 Diwali (Oct 20)
===============================================================================================================
Peak PM2.5                            612.9 µg/m³ (Nov 01 01:00)       960.7 µg/m³ (Oct 21 00:00)
Particulate surge vs daytime baseline  5.63x                            7.97x
Peak SO2 (combustion tracer)          80.06 µg/m³                     73.50 µg/m³
SO2 surge vs daytime baseline          7.91x                           5.34x
Return to ambient trajectory           ~18 hours                        ~20 hours
===============================================================================================================
```

The pulse lasts under 24 hours; the multi-week November baseline is a separate, seasonal phenomenon
that these data cannot attribute to any single driver.

---

## 7. Limitations

1. **No treatment variation.** The Delhi ban was in force in every year studied, so a ban effect is
   not identifiable. This is the binding constraint.
2. **No clean control unit.** Mumbai 2023–2025 hourly/daily data are unavailable, so DiD is not
   possible.
3. **Pre-trends violated and placebo significant**, so event-study and before/after estimates are
   biased toward finding an effect.
4. **AQI is pre-smoothed** (24h rolling average); PM2.5 is reported as the primary outcome for this
   reason.
5. **Measurement ceiling:** CAAQMS optical counters saturate near 1000 µg/m³ during the Diwali-night
   peak, so peak values are lower bounds.
6. **Mechanism claims are untested** (no PBLH, no fire counts).

---

## 8. Artifacts & Reproducibility

```
reports/causal/
├── diwali_ban_causal_analysis.md           <- this report
├── diwali_policy_status_timeline.csv       <- regulatory timeline
├── diwali_2025_daily_window.csv            <- 2025 ±14-day daily station panel
├── diwali_2024_daily_window.csv            <- 2024 ±14-day daily station panel
├── placebo_2025_daily_window.csv           <- Sep 2025 placebo panel
├── regression_models_summary.csv           <- coefficients, date-clustered SEs, se_type column
├── hourly_spike_comparison.csv             <- descriptive peak/tracer metrics
└── figures/                                <- regenerated when PostgreSQL is available
```

`src/analysis/diwali_causal_analysis.py` fits every regression with `cov_type='cluster'` grouped by
calendar date, reports both PM2.5 and AQI, and falls back to the cached daily CSVs when the database
is unavailable so the regression table can be regenerated offline.

---

## 9. Conclusion

The Diwali firecracker ban cannot be evaluated with the data in this repository: the ban was active
in all three observed years, pre-trends are violated, and a placebo test is significant. Naive
before/after comparisons produce large but non-credible numbers (e.g. +97 µg/m³ PM2.5), and once the
pre-existing seasonal trend is controlled the estimated level jump is statistically zero
(+16.95 µg/m³, p = 0.59 PM2.5; −10.59 AQI, p = 0.51). The defensible outputs of this study are the
methodological diagnosis and the descriptive hourly Diwali-night pulse — not a claim about the ban's
effect. Any statement that boundary-layer compression or stubble burning "caused" the post-Diwali
crisis remains an untested hypothesis until PBL height and fire-count data are added.

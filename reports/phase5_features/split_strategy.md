# Phase 5: Chronological Split Strategy

## 1. Rationale & Time-Series Partitioning Principles

Standard randomized $K$-fold cross-validation is categorically invalid for time-series forecasting because random shuffling breaks temporal dependency structures and introduces catastrophic lookahead bias (evaluating on past data after training on future data).

To rigorously evaluate real-world forecasting skill, Phase 5 implements a **strict chronological 3-way split** across the 2025 calendar year.

---

## 2. Partition Boundaries & Meteorological Coverage

```
┌────────────────────────────────────────────────────────┬───────────────────┬───────────────────┐
│                      TRAIN SET                         │  VALIDATION SET   │     TEST SET      │
│                2025-01-01 to 2025-08-31                │ 2025-09-01 to     │ 2025-11-01 to     │
│                       (8 Months)                       │ 2025-10-31        │ 2025-12-31        │
│                                                        │ (2 Months)        │ (2 Months)        │
└────────────────────────────────────────────────────────┴───────────────────┴───────────────────┘
 ◄────────────────────── 67.0% ─────────────────────────► ◄──── 16.5% ─────► ◄──── 16.5% ─────►
```

### Partition Breakdown

| Partition | Start Date (IST) | End Date (IST) | Duration | Seasons Represented | Operational / Evaluation Purpose |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Train** | `2025-01-01 00:00` | `2025-08-31 23:00` | 8 Months (243 days) | Late Winter, Pre-Monsoon / Summer, Peak Monsoon | Provides broad statistical exposure across atmospheric regimes: heavy stagnation, convective dust storms, and monsoon washout. |
| **Validation** | `2025-09-01 00:00` | `2025-10-31 23:00` | 2 Months (61 days) | Late Monsoon, Post-Monsoon (Onset of Stubble Burning) | Hyperparameter tuning, early stopping, and feature selection during the critical transition into high-pollution season. |
| **Test** | `2025-11-01 00:00` | `2025-12-31 23:00` | 2 Months (61 days) | Peak Severe Winter Stagnation & Fog Inversion | Out-of-sample ultimate stress test on hazardous air crisis conditions (GRAP Stages III & IV). |

---

## 3. Sample Counts & Target Availability per Split

| Split | Total Observations | 1-Hour Horizon Valid ($N$) | 6-Hours Horizon Valid ($N$) | 24-Hours Horizon Valid ($N$) |
| :--- | :---: | :---: | :---: | :---: |
| **Train** | 38,019 | 37,738 (99.26%) | 37,429 (98.45%) | 36,609 (96.29%) |
| **Validation** | 9,853 | 9,773 (99.19%) | 9,705 (98.50%) | 9,589 (97.32%) |
| **Test** | 10,074 | 9,972 (98.99%) | 9,855 (97.83%) | 9,552 (94.82%) |
| **Total** | **57,946** | **57,483 (99.20%)** | **56,989 (98.35%)** | **55,750 (96.21%)** |

---

## 4. Distribution Shift Across Splits

The chronological split intentionally reflects Delhi's real-world seasonal shifts:

- **Train Mean AQI:** Moderate baseline ($150\text{--}220$) encompassing summer dust and monsoon cleaning.
- **Validation Mean AQI:** Transition phase ($180\text{--}280$) showing rapid increases during October.
- **Test Mean AQI:** Extreme severe regime ($300\text{--}450+$) characterized by prolonged emergency episodes.

This distribution setup tests whether ML models can generalize forward in time without overfitting to low-pollution summer baselines.

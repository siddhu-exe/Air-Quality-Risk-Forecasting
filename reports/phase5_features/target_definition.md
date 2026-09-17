# Phase 5: Forecasting Target Definition & Horizon Availability

## 1. Problem Formulation & Mathematical Target Definition

The objective of the supervised forecasting pipeline in Phase 5 is to predict future continuous Air Quality Index (AQI) values across monitoring stations in Delhi, India, conditioned strictly on historical observations available at or prior to the forecast issuance timestamp $t$.

Let:
- $\mathcal{S} = \{s_1, s_2, \dots, s_7\}$ denote the set of 7 continuous ambient air quality monitoring stations (CAAQMS) in Delhi (`Anand Vihar`, `Bawana`, `Dwarka-Sector 8`, `ITO`, `Jahangirpuri`, `Punjabi Bagh`, `R K Puram`).
- $t \in \mathcal{T}$ denote the forecast generation timestamp (in regular 1-hour intervals on `Asia/Kolkata` time).
- $\mathbf{x}_{s, t} \in \mathbb{R}^d$ denote the causal feature vector constructed strictly from observations $\le t$.
- $Y_{s, t+h} \in \mathbb{R}^+$ denote the ground-truth target variable representing the future continuous AQI at station $s$ at lead time $h$ hours:

$$Y_{s, t+h} = \text{AQI}_{s, t+h}$$

The forecasting model learns a parameterized function $f_h: \mathbb{R}^d \to \mathbb{R}^+$ that minimizes the expected empirical error for horizon $h$:

$$\min_{\theta_h} \sum_{s \in \mathcal{S}} \sum_{t} \mathcal{L}\left( f_h(\mathbf{x}_{s, t}; \theta_h), Y_{s, t+h} \right)$$

where $\mathcal{L}$ is the primary loss function (e.g. Huber Loss / Squared Error / Absolute Error).

---

## 2. Rationale for Selected Forecasting Horizons

Three distinct forecasting horizons are formalized to serve operational, clinical, and regulatory decision windows:

| Horizon ($h$) | Target Notation | Operational Decision Window | Physical / Policy Rationale |
| :--- | :--- | :--- | :--- |
| **1-Hour Ahead** | $Y_{t+1} = \text{AQI}_{t+1}$ | **Immediate Health & Vulnerability Alerts** | Short-term persistence verification; detects sudden plume shifts, immediate morning/evening surge onset; provides real-time alerts for outdoor activities, commuters, and high-risk respiratory patients. |
| **6-Hours Ahead** | $Y_{t+6} = \text{AQI}_{t+6}$ | **Intra-Day Operational Adjustments** | Captures morning-to-afternoon photochemical transitions (Ozone buildup) and afternoon-to-evening nocturnal inversion collapse; enables intra-day municipal actions (e.g., localized water-sprinkling, anti-smog gun deployment, traffic routing). |
| **24-Hours Ahead** | $Y_{t+24} = \text{AQI}_{t+24}$ | **Next-Day Regulatory & GRAP Interventions** | Overcomes diurnal autocorrelation harmonics (full 24-hour solar cycle); directly aligns with the Commission for Air Quality Management (CAQM) Graded Response Action Plan (GRAP Stages I–IV: school closures, truck entry bans, construction halts, odd-even vehicle rationing). |

---

## 3. Empirical Target Availability & Network Coverage

Target availability was audited across all 57,946 ground-truth AQI records in PostgreSQL (`air_quality_db` on port 5433) for the calendar year 2025 across all 7 Delhi stations.

### Network-Wide Summary

| Metric | 1-Hour Horizon ($h=1$) | 6-Hours Horizon ($h=6$) | 24-Hours Horizon ($h=24$) |
| :--- | :---: | :---: | :---: |
| **Total Base Observations ($N$)** | 57,946 | 57,946 | 57,946 |
| **Available Future Targets ($N_{valid}$)** | 57,483 | 56,989 | 55,750 |
| **Network Target Coverage (%)** | **99.20%** | **98.35%** | **96.21%** |
| **Missing Target Records** | 463 | 957 | 2,196 |

---

### Station-Level Target Availability

| Station Name | Base AQI Observations | $h=1$ Avail (Count) | $h=1$ Coverage (%) | $h=6$ Avail (Count) | $h=6$ Coverage (%) | $h=24$ Avail (Count) | $h=24$ Coverage (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Anand Vihar** | 8,130 | 8,061 | 99.15% | 7,963 | 97.95% | 7,695 | 94.65% |
| **Bawana** | 8,598 | 8,539 | 99.31% | 8,503 | 98.90% | 8,418 | 97.91% |
| **Dwarka-Sector 8** | 8,454 | 8,393 | 99.28% | 8,337 | 98.62% | 8,197 | 96.96% |
| **ITO** | 8,181 | 8,115 | 99.19% | 8,048 | 98.37% | 7,878 | 96.30% |
| **Jahangirpuri** | 8,501 | 8,438 | 99.26$ | 8,391 | 98.71% | 8,275 | 97.34% |
| **Punjabi Bagh** | 7,838 | 7,766 | 99.08% | 7,671 | 97.87% | 7,457 | 95.14% |
| **R K Puram** | 8,244 | 8,171 | 99.11% | 8,076 | 97.96% | 7,830 | 94.98% |

---

### Monthly Network Target Availability (2025)

| Year | Month | Base Observations | $h=1$ Avail (%) | $h=6$ Avail (%) | $h=24$ Avail (%) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2025 | January | 4,498 | 99.49% | 98.58% | 95.26% |
| 2025 | February | 4,374 | 99.75% | 98.54% | 95.15% |
| 2025 | March | 5,043 | 99.11% | 98.59% | 97.48% |
| 2025 | April | 4,851 | 98.87% | 98.21% | 96.74% |
| 2025 | May | 4,951 | 99.19% | 98.12% | 96.14% |
| 2025 | June | 4,688 | 99.02% | 97.63% | 95.20% |
| 2025 | July | 4,808 | 99.25% | 98.04% | 95.09% |
| 2025 | August | 4,775 | 98.83% | 97.42% | 94.43% |
| 2025 | September | 4,882 | 98.91% | 98.61% | 97.66% |
| 2025 | October | 4,971 | 98.99% | 98.49% | 97.00% |
| 2025 | November | 4,959 | 99.52% | 99.23% | 98.43% |
| 2025 | December | 5,146 | 99.53% | 98.66% | 95.59% |

---

## 4. Target Alignment & Missingness Protocol

1. **Alignment Criterion:** For any sample $(s, t)$ in the dataset, a valid training/evaluation instance for horizon $h$ requires both:
   - A valid feature vector $\mathbf{x}_{s, t}$ computed from data $\le t$.
   - A non-null ground-truth target measurement $\text{AQI}_{s, t+h}$ at exactly $t+h$.
2. **Missing Target Handling:** 
   - Instances where $\text{AQI}_{s, t+h}$ is null/missing are dropped from training and evaluation for horizon $h$ only (they are **never** forward-filled or interpolated with artificial targets).
   - This ensures 100% empirical authenticity in evaluation metrics across all horizons.

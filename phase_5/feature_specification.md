# Phase 5: Feature Engineering Specification

## 1. Architectural Overview

The Phase 5 feature engineering architecture transforms raw CAAQMS sensor measurements and AQI observations into a unified, tabular, leakage-free feature matrix for multi-horizon supervised regression ($\text{AQI}(t+1), \text{AQI}(t+6), \text{AQI}(t+24)$).

Each row represents an observation at station $s \in \mathcal{S}$ at timestamp $t$. All features $\mathbf{x}_{s, t} \in \mathbb{R}^{124}$ are constructed strictly using information available at or before timestamp $t$ ($\tau \le t$).

---

## 2. Feature Group Specifications

```
                           ┌────────────────────────────────────────┐
                           │      FEATURE MATRIX (124 FEATURES)     │
                           └────────────────────────────────────────┘
                                               │
     ┌─────────────────┬─────────────────┬─────┴───────────┬─────────────────┬─────────────────┐
     ▼                 ▼                 ▼                 ▼                 ▼                 ▼
 ┌───────┐         ┌───────┐         ┌───────┐         ┌───────┐         ┌───────┐         ┌───────┐
 │Group A│         │Group B│         │Group C│         │Group D│         │Group E│         │Group F│
 │AQI    │         │Pollut.│         │Rolling│         │Cyclic │         │Season │         │Meteo  │
 │Lags   │         │Lags   │         │Stats  │         │Time   │         │Indics │         │Drivers│
 │(10)   │         │(35)   │         │(32)   │         │(13)   │         │(4)    │         │(24)   │
 └───────┘         └───────┘         └───────┘         └───────┘         └───────┘         └───────┘
                                                           │
                                                           ▼
                                                       ┌───────┐
                                                       │Group G│
                                                       │Spatial│
                                                       │Network│
                                                       │(6)    │
                                                       └───────┘
```

---

### Group A: Recent AQI Lags & Current Index (10 Features)

Captures the high autoregressive persistence of AQI ($r \approx 0.998$ at lag-1h, $r \approx 0.77$ at lag-168h):

| Feature Name | Definition / Formulation | Rationale |
| :--- | :--- | :--- |
| `aqi_curr` | $\text{AQI}_{s}(t)$ | Current baseline AQI at forecast issuance time $t$. |
| `aqi_lag_1h` | $\text{AQI}_{s}(t-1)$ | Immediate prior hour AQI. |
| `aqi_lag_2h` | $\text{AQI}_{s}(t-2)$ | 2-hour prior lag. |
| `aqi_lag_3h` | $\text{AQI}_{s}(t-3)$ | 3-hour prior lag. |
| `aqi_lag_6h` | $\text{AQI}_{s}(t-6)$ | 6-hour prior lag (intra-day baseline). |
| `aqi_lag_12h` | $\text{AQI}_{s}(t-12)$ | Half-day prior lag. |
| `aqi_lag_24h` | $\text{AQI}_{s}(t-24)$ | 1-day prior lag (primary diurnal harmonic anchor). |
| `aqi_lag_48h` | $\text{AQI}_{s}(t-48)$ | 2-day prior lag. |
| `aqi_lag_72h` | $\text{AQI}_{s}(t-72)$ | 3-day prior lag. |
| `aqi_lag_168h` | $\text{AQI}_{s}(t-168)$ | 1-week prior lag (weekly recurrence cycle). |

---

### Group B: Multi-Pollutant Lags & Current Values (35 Features)

Monitors the chemical precursor state and secondary aerosol drivers across 7 primary criteria pollutants: $\mathcal{P} = \{\text{PM}_{2.5}, \text{PM}_{10}, \text{NO}_2, \text{NO}_x, \text{SO}_2, \text{CO}, \text{O}_3\}$.

For each pollutant $p \in \mathcal{P}$, 5 features are extracted:
- `p_curr`: Value at time $t$
- `p_lag_1h`: Value at time $t-1$
- `p_lag_6h`: Value at time $t-6$
- `p_lag_12h`: Value at time $t-12$
- `p_lag_24h`: Value at time $t-24$

Total features: $7 \text{ pollutants} \times 5 = 35 \text{ features}$.

---

### Group C: Causal Backward Rolling Statistics (32 Features)

Computes statistical momentum, moving trend, and localized dispersion over backward-looking windows $W \in \{3\text{h}, 6\text{h}, 12\text{h}, 24\text{h}\}$ evaluated over the closed interval $[t-W+1, t]$.

For both $\text{AQI}$ and $\text{PM}_{2.5}$, 4 statistical aggregations are computed per window $W$:
1. **Rolling Mean:** $\mu_{W}(t) = \frac{1}{W}\sum_{k=0}^{W-1} x(t-k)$
2. **Rolling Std Dev:** $\sigma_{W}(t) = \sqrt{\frac{1}{W-1}\sum_{k=0}^{W-1} (x(t-k) - \mu_W(t))^2}$
3. **Rolling Minimum:** $\min_{k \in [0, W-1]} x(t-k)$
4. **Rolling Maximum:** $\max_{k \in [0, W-1]} x(t-k)$

Total features: $2 \text{ variables} \times 4 \text{ windows} \times 4 \text{ aggregations} = 32 \text{ features}$.

---

### Group D: Temporal & Cyclical Encodings (13 Features)

Encodes periodic time cycles without artificial boundary discontinuities (e.g. bridging 23:00 to 00:00, Sunday to Monday, Dec to Jan):

| Feature Name | Formulation | Range |
| :--- | :--- | :---: |
| `hour` | Integer hour of day | $0 \dots 23$ |
| `day_of_week` | Integer day of week (Monday=0) | $0 \dots 6$ |
| `month` | Integer month of year | $1 \dots 12$ |
| `day_of_year` | Integer day of calendar year | $1 \dots 365$ |
| `is_weekend` | $\mathbb{I}(\text{day\_of\_week} \ge 5)$ | $\{0, 1\}$ |
| `sin_hour` / `cos_hour` | $\sin(2\pi \cdot \text{hour}/24)$, $\cos(2\pi \cdot \text{hour}/24)$ | $[-1, +1]$ |
| `sin_dow` / `cos_dow` | $\sin(2\pi \cdot \text{dow}/7)$, $\cos(2\pi \cdot \text{dow}/7)$ | $[-1, +1]$ |
| `sin_month` / `cos_month` | $\sin(2\pi \cdot (\text{month}-1)/12)$, $\cos(2\pi \cdot (\text{month}-1)/12)$ | $[-1, +1]$ |
| `sin_doy` / `cos_doy` | $\sin(2\pi \cdot (\text{doy}-1)/365.25)$, $\cos(2\pi \cdot (\text{doy}-1)/365.25)$ | $[-1, +1]$ |

---

### Group E: IMD Seasonality Indicators (4 Features)

One-hot binary indicators matching the Indian Meteorological Department (IMD) four-season framework validated in Phase 4 EDA:

- `is_winter`: $\mathbb{I}(\text{month} \in \{12, 1, 2\})$ — Peak planetary boundary layer compression and severe stagnation.
- `is_summer`: $\mathbb{I}(\text{month} \in \{3, 4, 5\})$ — High convective mixing, dust storms, elevated daytime temperatures.
- `is_monsoon`: $\mathbb{I}(\text{month} \in \{6, 7, 8, 9\})$ — Precipitation wash-out, high humidity, lowest annual baseline pollution.
- `is_post_monsoon`: $\mathbb{I}(\text{month} \in \{10, 11\})$ — Agricultural stubble burning, festive emissions, onset of thermal inversion.

---

### Group F: Meteorological Features (24 Features)

Includes the 4 primary physical atmospheric variables validated for ML usability in Phase 4: Temperature (`temp`), Relative Humidity (`humidity`), Wind Speed (`wind_speed`), and Solar Radiation (`solar_rad`).

For each meteorological variable $m \in \{\text{temp}, \text{humidity}, \text{wind\_speed}, \text{solar\_rad}\}$:
- `m_curr`: Current observation at time $t$
- `m_lag_1h`: Lagged value at $t-1$
- `m_lag_6h`: Lagged value at $t-6$
- `m_lag_24h`: Lagged value at $t-24$
- `m_roll_mean_6h`: 6-hour backward rolling mean
- `m_roll_mean_24h`: 24-hour backward rolling mean

*Exclusions:* Rainfall (56.6% missing rate) and Xylene (100% missing rate) are excluded based on Phase 4 EDA quality gates.

Total features: $4 \text{ variables} \times 6 \text{ transformations} = 24 \text{ features}$.

---

### Group G: Cross-Station Spatial Network Signals (6 Features)

Leverages the high inter-station airshed synchronization ($r \ge 0.92$ for AQI across Delhi) using strictly lagged $(\le t-1)$ regional measurements:

| Feature Name | Mathematical Definition | Physical Meaning |
| :--- | :--- | :--- |
| `network_mean_aqi_lag_1h` | $\frac{1}{|\mathcal{S}|-1}\sum_{s' \neq s} \text{AQI}_{s'}(t-1)$ | Citywide average prior-hour AQI excluding target station $s$. |
| `network_mean_pm25_lag_1h` | $\frac{1}{|\mathcal{S}|-1}\sum_{s' \neq s} \text{PM}_{2.5, s'}(t-1)$ | Citywide average prior-hour $\text{PM}_{2.5}$ excluding target station $s$. |
| `network_max_aqi_lag_1h` | $\max_{s' \in \mathcal{S}} \text{AQI}_{s'}(t-1)$ | Network peak prior-hour AQI (tracks regional pollution hotspot emergence). |
| `network_min_aqi_lag_1h` | $\min_{s' \in \mathcal{S}} \text{AQI}_{s'}(t-1)$ | Network cleanest prior-hour AQI (tracks regional background baseline). |
| `top_neighbor_aqi_lag_1h` | $\text{AQI}_{\text{neighbor}(s)}(t-1)$ | Prior-hour AQI of the highest-correlated spatial neighbor station. |
| `top_neighbor_pm25_lag_1h` | $\text{PM}_{2.5, \text{neighbor}(s)}(t-1)$ | Prior-hour $\text{PM}_{2.5}$ of the highest-correlated spatial neighbor station. |

*Top Neighbor Mapping:*
- Anand Vihar $\to$ Dwarka-Sector 8 ($r=0.954$)
- Bawana $\to$ R K Puram ($r=0.967$)
- Dwarka-Sector 8 $\to$ R K Puram ($r=0.976$)
- ITO $\to$ R K Puram ($r=0.962$)
- Jahangirpuri $\to$ Bawana ($r=0.959$)
- Punjabi Bagh $\to$ R K Puram ($r=0.976$)
- R K Puram $\to$ Punjabi Bagh ($r=0.976$)

---

## 3. Summary of Manifest & Data Types

- **Total Engineered Feature Columns:** 124
- **Observation Count:** 57,946 rows
- **Output Storage:** `data/processed/features_2025.parquet`
- **Metadata Manifest:** `reports/features/feature_manifest.csv`

# Phase 5: Leakage Prevention & Causal Integrity Audit

## 1. Executive Summary & Audit Verdict

A systematic audit was conducted on the Phase 5 feature engineering architecture and dataset generation pipeline (`src/features/build_features.py`) to verify that all predictive modeling features strictly observe temporal causality.

**Audit Verdict:** **PASSED (ZERO LEAKAGE DETECTED)**
- All 124 engineered feature variables are constructed strictly from observations $\tau \le t$.
- Target variables for all forecasting horizons ($h \in \{1, 6, 24\}$) are strictly forward-shifted ($\tau = t+h$).
- Spatial network features strictly use lagged measurements ($\tau \le t-1$) with explicit leave-one-out self-exclusion.
- Preprocessing and model training boundaries are strictly isolated to the training window ($t \le \text{2025-08-31 23:00:00}$).

---

## 2. Causal Horizon Matrix & Mathematical Proof

For any given forecast issuance timestamp $t$ at station $s \in \mathcal{S}$:

$$\mathbf{x}_{s, t} = \Phi\left( \{\mathbf{Z}_{s', \tau} \mid s' \in \mathcal{S}, \tau \le t\} \right)$$

where $\mathbf{Z}_{s', \tau}$ represents the raw multivariate sensor measurements and AQI values at station $s'$ at historical time $\tau$.

| Component | Temporal Index ($\tau$) | Status | Verification Protocol |
| :--- | :---: | :---: | :--- |
| **Current Target State** (`aqi_curr`) | $\tau = t$ | Valid Input | Represents the latest observed AQI state available when issuing forecasts at time $t$. |
| **Autoregressive Lags** (`aqi_lag_*h`, `p_lag_*h`) | $\tau \in \{t-1, t-2, \dots, t-168\}$ | Valid Input | Computed via positive integer time-series shifts: `series.shift(lag)`. |
| **Rolling Window Statistics** (`*_roll_*`) | $\tau \in [t-W+1, t]$ | Valid Input | Computed via backward-looking rolling windows (`center=False`). |
| **Cyclical & Calendar Time** (`hour`, `dow`, `month`) | $\tau = t$ | Valid Input | Deterministic calendar attributes known a priori at time $t$. |
| **Spatial Network Aggregates** (`network_*`, `top_neighbor_*`) | $\tau \le t-1$ | Valid Input | Leave-one-out network aggregation computed strictly on `lag_1h` series. |
| **Forecasting Targets** (`target_aqi_1h`, `target_aqi_6h`, `target_aqi_24h`) | $\tau \in \{t+1, t+6, t+24\}$ | Ground Truth Only | Computed via negative integer time-series shifts: `series.shift(-h)`. Never included in feature matrix $\mathbf{X}$. |

---

## 3. Detailed Audit Dimensions

### A. Backward-Looking Rolling Aggregation
- **Risk:** If rolling windows use `center=True` or incorporate future timestamps ($t+1, \dots$), future information bleeds into current features.
- **Verification:** In `src/features/build_features.py`, rolling aggregates are defined as:
  ```python
  series.rolling(window=w, min_periods=min_p).mean()
  ```
  In Pandas, default rolling evaluation is strictly trailing (`center=False`), evaluating strictly over $[t-w+1, t]$. No lookahead occurs.

### B. Spatial Network Aggregation & Self-Exclusion
- **Risk:** Computing network-wide mean AQI at time $t$ could inadvertently leak the target station's current AQI if unlagged, or leak current network values across stations before local transmission.
- **Verification:**
  1. All spatial network aggregates (`network_mean_aqi_lag_1h`, `network_mean_pm25_lag_1h`, `network_max_aqi_lag_1h`, `network_min_aqi_lag_1h`) are computed strictly from `aqi_lag_1h` and `pm25_lag_1h` ($\tau = t-1$).
  2. The target station's own lagged value is subtracted from the network total to ensure pure leave-one-out spatial independence:
     $$\mu_{-s, t-1} = \frac{\sum_{s'} \text{lag1}_{s', t-1} - \text{lag1}_{s, t-1}}{N_{valid} - 1}$$
  3. Top-correlated neighbor features (`top_neighbor_aqi_lag_1h`, `top_neighbor_pm25_lag_1h`) strictly reference the neighbor station's state at $\tau = t-1$.

### C. Cold-Start Boundary Preservation (2024 to 2025 Transition)
- **Risk:** When engineering lag-168h (1 week) or rolling 24h features on Jan 1, 2025, truncated datasets create artificial missingness or fill forward with mean imputations.
- **Verification:** The SQL extraction in `build_features.py` queries CAAQMS data starting from **`2023-12-31 18:30:00+00`** (2024-01-01 00:00:00 IST), maintaining a full 1-year historical warm-up buffer prior to the 2025 modeling window.

### D. Chronological Partitioning & Preprocessor Isolation
- **Risk:** Fitting scalers, imputers, or encoders across the entire dataset leaks validation and test statistics (mean, variance, distribution shape) into the training phase.
- **Verification:**
  1. Dataset splitting is strictly chronological:
     - **Train:** Jan 1, 2025 – Aug 31, 2025
     - **Validation:** Sep 1, 2025 – Oct 31, 2025
     - **Test:** Nov 1, 2025 – Dec 31, 2025
  2. Any normalization, imputation, or pipeline transformations are fit strictly on the Training slice ($t \le \text{2025-08-31}$) and applied downstream to Validation and Test via transform-only interfaces.
  3. No cross-validation folds allow training on future chunks to predict past chunks (e.g. no random K-Fold).

---

## 4. Summary Checklist

- [x] Target variables are strictly shifted forward ($t+1, t+6, t+24$).
- [x] Target variables are separated and excluded from feature matrices $\mathbf{X}$.
- [x] All rolling window operations are strictly backward-looking (`center=False`).
- [x] Autoregressive lags use positive shift offsets ($\ge 1$).
- [x] Cross-station spatial signals use strictly lagged values ($\le t-1$).
- [x] Station self-exclusion is enforced for network-wide aggregates.
- [x] 2024 historical warm-up buffer prevents boundary cold-start truncation.
- [x] Train/Validation/Test splits are strictly chronological.
- [x] No future-target interpolation or synthetic target imputation is performed.

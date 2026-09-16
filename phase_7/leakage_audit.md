# Phase 7 Leakage Audit & Control Plan

**Document Version:** 1.0  
**Status:** DRAFT — Design & Specification Phase  
**Date:** 2026-09-16  
**Depends On:** `phase_7/target_definition.md`

---

## 1. Purpose

This document outlines the strict controls required to prevent data leakage during Phase 7 (CPCB Risk Classification & GRAP Alerting). While Phase 5/6 focused on feature and temporal leakage, Phase 7 focuses on **methodological and evaluative leakage** — preventing the test set from influencing the classification logic or alert definitions.

---

## 2. Identified Leakage Vectors for Phase 7

If not controlled, the following practices would invalidate the Phase 7 results:

1. **Threshold Fitting:** Optimizing CPCB or GRAP boundaries to maximize F1 or Recall on the test set, rather than using official strict regulatory thresholds.
2. **Forecast Calibration:** Scaling, shifting, or adjusting the frozen Phase 6 continuous forecasts to improve classification metrics on the test set.
3. **Observation-Based Alerting:** Using actual AQI observations ($y_{true}$) to trigger early warning GRAP alerts, rather than purely relying on forecasts ($\hat{y}$).
4. **Data Leakage in Episode Definitions:** Defining "episodes" based on complex look-ahead/look-behind logic that uses future knowledge to classify current state (e.g., smoothing actuals before comparing to thresholds).
5. **Modification of Phase 6 Artifacts:** Any alteration to the frozen prediction parquet files.

---

## 3. Strict Audit Controls

### 3.1 CPCB Threshold Control (No Fitting)
- **Constraint:** CPCB category boundaries MUST be implemented strictly as defined by the 2014 CPCB notification.
  - Good (0), Satisfactory (51), Moderate (101), Poor (201), Very Poor (301), Severe (401)
- **Audit Verification:** The Python binning function `np.digitize()` or `pd.cut()` must use hardcoded boundary arrays derived directly from the official specification. No variable thresholds (`threshold_param`) are permitted.

### 3.2 Phase 6 Prediction Integrity
- **Constraint:** The input prediction arrays (`prediction_hybrid_6c_winning`, `y_pred` for 1h/6h) must be read directly from the audited parquet files and used without modification.
- **Audit Verification:** No scalers, offsets (e.g., bias correction), Platt scaling, or isotonic regression may be applied to the continuous forecasts before binning.

### 3.3 Forecast-Based Alert Logic (Zero-Actuals)
- **Constraint:** The boolean columns representing GRAP alerts (e.g., `stage_iii_alert`, `stage_iv_alert`) must be computed **entirely** as functions of $\hat{y}$ (the forecast column).
- **Audit Verification:** Code review must confirm that $y_{true}$ (the actual AQI) is heavily isolated and used ONLY in the `sklearn.metrics` functions or custom evaluation scoring functions, NEVER in the alert generation functions.

### 3.4 Episode Detection Causality
- **Constraint:** When measuring lead times, the "Forecast Crossing Timestamp" must correspond to a forecast that was physically available at or before the onset of the episode.
- **Audit Verification:** Since the prediction columns inherently represent $t+h$ (e.g., a prediction for 14:00 generated at 13:00 for the 1h horizon), comparing the prediction timestamp directly to the actual occurrence timestamp is inherently causal.

---

## 4. Required Assertions in Phase 7 Implementation Code

The underlying implementation script (to be written after Phase 7 design approval) must contain the following runtime assertions:

```python
# 1. Ensure exactly 6 unique classes are possible in predictions
assert set(predicted_classes).issubset({0, 1, 2, 3, 4, 5})

# 2. Ensure target columns are strictly untouched (no missing values filled by mean, etc.)
assert df['target_aqi_24h'].isnull().sum() == 0

# 3. Ensure no actual AQI informs the alert columns
# (Alerts should be perfectly derivable just from the predictions)
assert (df['prediction_hybrid_6c_winning'] >= 451).equals(df['stage_iv_alert_forecast'])
```

---

## 5. Summary

Phase 7 is entirely deterministic. By treating the CPCB and CAQM regulations as immutable mathematical functions, and evaluating them purely against the previously frozen Phase 6 predictions, we guarantee zero methodological leakage.

---
**Next Document:** `phase_7/phase_7_plan.md` — Final assembly of the master plan and verdict.
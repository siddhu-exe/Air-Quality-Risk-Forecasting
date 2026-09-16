# Phase 7 Risk Classification Specification

**Document Version:** 1.0  
**Status:** DRAFT — Design & Specification Phase  
**Date:** 2026-09-16  
**Depends On:** `phase_7/target_definition.md`

---

## 1. Purpose

This document specifies the **multi-class CPCB AQI risk classification** methodology for Phase 7. The task is to convert frozen Phase 6 continuous AQI forecasts into the official 6-tier CPCB risk categories, evaluate classification performance, and quantify degradation across horizons.

**Critical Design Principle:** **No model training.** Classification is a deterministic post-processing step (binning) applied to frozen Phase 6 predictions.

---

## 2. Classification Task Definition

### 2.1 Formal Problem Statement

Given:
- Frozen Phase 6 predictions $\hat{y}^{(h)}$ for horizons $h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$ on the held-out test set (Nov–Dec 2025)
- Actual observed AQI values $y_{true}^{(h)}$ for the same test set

**Task:** Map both $\hat{y}^{(h)}$ and $y_{true}^{(h)}$ to CPCB categories using the deterministic binning function, then evaluate the multi-class classification performance.

### 2.2 CPCB Category Encoding

| Class Index | Category | AQI Range | Ordinal Rank |
|---|---|---|---|
| 0 | Good | [0, 51) | 0 (best) |
| 1 | Satisfactory | [51, 101) | 1 |
| 2 | Moderate | [101, 201) | 2 |
| 3 | Poor | [201, 301) | 3 |
| 4 | Very Poor | [301, 401) | 4 |
| 5 | Severe | [401, 501] | 5 (worst) |

**Encoding:** Ordinal integer 0–5. This preserves the natural ordering for ordinal metrics.

### 2.3 Deterministic Binning Function

```python
import numpy as np

CPCB_BOUNDARIES = np.array([0, 51, 101, 201, 301, 401, 501])
CPCB_LABELS = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor', 'Severe']

def cpcb_classify(aqi_values: np.ndarray) -> np.ndarray:
    """
    Deterministic CPCB binning. Vectorized for batch evaluation.
    
    Args:
        aqi_values: Array of continuous AQI values (can be predictions or actuals)
    
    Returns:
        Array of class indices 0-5
    """
    # np.digitize returns index of bin: [0, 51) -> 1, [51, 101) -> 2, etc.
    # Subtract 1 to get 0-indexed classes
    return np.digitize(aqi_values, CPCB_BOUNDARIES[1:-1], right=False)
    # Equivalent to:
    # classes = np.zeros_like(aqi_values, dtype=int)
    # classes[aqi_values >= 401] = 5  # Severe
    # classes[(aqi_values >= 301) & (aqi_values < 401)] = 4  # Very Poor
    # classes[(aqi_values >= 201) & (aqi_values < 301)] = 3  # Poor
    # classes[(aqi_values >= 101) & (aqi_values < 201)] = 2  # Moderate
    # classes[(aqi_values >= 51) & (aqi_values < 101)] = 1  # Satisfactory
    # classes[aqi_values < 51] = 0  # Good
    # return classes
```

**Properties:**
- Pure function: no state, no learned parameters
- Idempotent: `cpcb_classify(cpcb_classify(x))` = `cpcb_classify(x)` (with inverse mapping)
- Order-preserving: if $a < b$ then `class(a)` ≤ `class(b)`

---

## 3. Multi-Class Evaluation Metrics

### 3.1 Primary Metrics (Per Horizon)

| Metric | Formula / Description | Why It Matters |
|--------|----------------------|----------------|
| **Macro F1** | $\frac{1}{6}\sum_{k=0}^{5} F1_k$ | Equal weight per class; critical for rare Severe class |
| **Weighted F1** | $\sum_{k=0}^{5} \frac{N_k}{N} F1_k$ | Accounts for class imbalance (Good/Moderate dominate) |
| **Per-Class Precision** | $\frac{TP_k}{TP_k + FP_k}$ | False alarms in Severe class are costly |
| **Per-Class Recall** | $\frac{TP_k}{TP_k + FN_k}$ | Missing Severe episodes is critical failure |
| **Confusion Matrix** | $C_{ij} = \text{count}(y_{true}=i, \hat{y}=j)$ | Visualize misclassification patterns (adjacent vs distant) |
| **Cohen's Weighted Kappa** | $\kappa_w = 1 - \frac{\sum_{i,j} w_{ij} O_{ij}}{\sum_{i,j} w_{ij} E_{ij}}$ | Ordinal agreement; quadratic weights penalize distant errors more |
| **Ordinal MAE** | $\frac{1}{N}\sum |\text{class}(y_{true}) - \text{class}(\hat{y})|$ | Average category distance error |

### 3.2 Severe-Class Focused Metrics

| Metric | Definition |
|--------|------------|
| **Severe F1 (Class 5)** | F1 score specifically for Severe (AQI ≥ 401) |
| **Severe Recall (Sensitivity)** | $\frac{TP_{Severe}}{TP_{Severe} + FN_{Severe}}$ — what fraction of actual Severe episodes were caught |
| **Severe Precision** | $\frac{TP_{Severe}}{TP_{Severe} + FP_{Severe}}$ — what fraction of predicted Severe were actually Severe |
| **Very Poor + Severe Recall** | Recall for classes {4, 5} combined (AQI ≥ 301) |
| **Critical Miss Rate** | $\frac{\text{Actual Severe predicted as ≤ Moderate}}{\text{Total Actual Severe}}$ — catastrophic under-prediction |

### 3.3 Horizon Comparative Metrics

| Comparison | Purpose |
|------------|---------|
| 1h vs 6h vs 24h Macro F1 | Quantify classification degradation with horizon |
| 1h vs 6h vs 24h Severe Recall | Early warning capability decay |
| Confusion matrix drift | How misclassification patterns shift (e.g., 24h: Severe→Very Poor vs 1h: Severe→Severe) |

---

## 4. Class Imbalance Analysis

**Expected Test Set Distribution (from Phase 6 EDA, Nov–Dec 2025):**

| Class | Category | Approx % | Approx Count (24h test, N=9800) |
|-------|----------|----------|----------------------------------|
| 0 | Good | ~5% | ~490 |
| 1 | Satisfactory | ~15% | ~1,470 |
| 2 | Moderate | ~25% | ~2,450 |
| 3 | Poor | ~25% | ~2,450 |
| 4 | Very Poor | ~20% | ~1,960 |
| 5 | Severe | ~10% | ~980 |

**Implications:**
- Macro F1 is preferred over accuracy (accuracy ~65% baseline from majority class)
- Severe class (~10%) needs explicit focus — weighted metrics will under-represent it
- Confusion matrices must be normalized per-row (recall view) AND per-column (precision view)

---

## 5. Misclassification Cost Matrix (Ordinal-Aware)

| True \ Pred | Good (0) | Satis (1) | Mod (2) | Poor (3) | V.Poor (4) | Severe (5) |
|---|---|---|---|---|---|---|
| **Good (0)** | 0 | 1 | 2 | 3 | 4 | 5 |
| **Satisfactory (1)** | 1 | 0 | 1 | 2 | 3 | 4 |
| **Moderate (2)** | 2 | 1 | 0 | 1 | 2 | 3 |
| **Poor (3)** | 3 | 2 | 1 | 0 | 1 | 2 |
| **Very Poor (4)** | 4 | 3 | 2 | 1 | 0 | 1 |
| **Severe (5)** | 5 | 4 | 3 | 2 | 1 | 0 |

**Cost Interpretation:**
- **Adjacent misclassification (cost=1)**: Acceptable (e.g., Poor ↔ Very Poor)
- **Distant misclassification (cost≥3)**: Concerning (e.g., Severe ↔ Moderate)
- **Catastrophic (cost=5)**: Severe predicted as Good or vice versa

**Weighted Kappa Weights:** Use quadratic weights $w_{ij} = (i-j)^2 / (K-1)^2$ where $K=6$.

---

## 6. Per-Horizon Specification

### 6.1 1-Hour Horizon
- **Input:** `data/Artifacts/1h/predictions_1h_test.parquet` (10,057 rows)
- **Columns:** `y_true` (actual), `y_pred` (LightGBM prediction)
- **Expected Performance:** High (MAE=2.29 AQI → most errors within 1 category)
- **Key Question:** Does near-perfect regression translate to near-perfect classification?

### 6.2 6-Hour Horizon
- **Input:** `data/Artifacts/6h/predictions_6h_test.parquet` (9,998 rows)
- **Columns:** `y_true`, `y_pred` (LightGBM prediction)
- **Expected Performance:** Good (MAE=11.84 AQI → occasional 1-category errors, rare 2-category)
- **Key Question:** How often does 6h forecast cross category boundaries incorrectly?

### 6.3 24-Hour Horizon
- **Input:** `reports/modeling/24h/final/final_predictions.parquet` (9,800 rows)
- **Columns:** `target_aqi_24h` (actual), `prediction_hybrid_6c_winning` (Hybrid prediction)
- **Expected Performance:** Moderate (MAE=34.11 AQI → frequent 1-category errors, some 2-category)
- **Key Question:** Is 24h classification still actionable for GRAP early warning?

---

## 7. Output Schema

### 7.1 Per-Row Classification Results (Parquet)

| Column | Type | Description |
|--------|------|-------------|
| `station_id` | int64 | Station identifier |
| `station_name` | string | Station name |
| `timestamp` | datetime64[ns, UTC] | Forecast issuance time |
| `horizon` | string | '1h' \| '6h' \| '24h' |
| `aqi_actual` | float64 | Observed AQI at $t+h$ |
| `aqi_predicted` | float64 | Phase 6 model prediction |
| `category_actual` | int8 | CPCB class 0–5 (actual) |
| `category_predicted` | int8 | CPCB class 0–5 (predicted) |
| `category_name_actual` | string | Category label |
| `category_name_predicted` | string | Category label |
| `is_correct` | bool | Exact category match |
| `ordinal_error` | int8 | $\text{class}_{pred} - \text{class}_{actual}$ |
| `abs_ordinal_error` | uint8 | $|\text{ordinal_error}|$ |
| `severe_actual` | bool | $\text{aqi_actual} \ge 401$ |
| `severe_predicted` | bool | $\text{aqi_predicted} \ge 401$ |
| `vpoor_plus_actual` | bool | $\text{aqi_actual} \ge 301$ |
| `vpoor_plus_predicted` | bool | $\text{aqi_predicted} \ge 301$ |

### 7.2 Aggregate Metrics (CSV)

**`multiclass_metrics_{horizon}.csv`:**
| Metric | Value |
|--------|-------|
| macro_f1 | float |
| weighted_f1 | float |
| macro_precision | float |
| macro_recall | float |
| weighted_kappa | float |
| ordinal_mae | float |
| severe_f1 | float |
| severe_recall | float |
| severe_precision | float |
| vpoor_plus_recall | float |
| critical_miss_rate | float |

**`confusion_matrix_{horizon}.csv`:** 6×6 matrix with row/col labels

---

## 8. Leakage Controls (Classification-Specific)

| Control | Implementation |
|---------|----------------|
| **No threshold tuning** | CPCB boundaries are fixed by regulation — no optimization on test set |
| **No class balancing** | Evaluation on natural distribution; no SMOTE, no class weights |
| **No learned mapping** | Binning is deterministic; no calibration, no Platt scaling |
| **Actuals only for evaluation** | `y_true` used solely to compute metrics; never feeds back into prediction |
| **Frozen Phase 6 predictions** | Classification uses exact predictions from Phase 6 audit artifacts |

---

## 9. Visualization Requirements

| Plot | Purpose |
|------|---------|
| Confusion matrix heatmap (normalized row-wise) | Recall per class |
| Confusion matrix heatmap (normalized col-wise) | Precision per class |
| Ordinal error distribution (histogram) | Error magnitude profile |
| Per-horizon macro F1 bar chart | Horizon degradation |
| Severe class recall vs horizon | Early warning decay |
| Misclassification flow: Actual → Predicted category | Sankey/flow diagram |

---

## 10. Acceptance Criteria

- [ ] Deterministic binning function implemented and tested against CPCB boundaries
- [ ] All 7 primary metrics computed per horizon
- [ ] Severe-class focused metrics reported
- [ ] Confusion matrices generated (raw + normalized)
- [ ] Weighted Kappa with quadratic weights computed
- [ ] Ordinal MAE reported
- [ ] Per-row classification results saved as Parquet
- [ ] Aggregate metrics saved as CSV
- [ ] Cross-horizon comparison table generated
- [ ] Zero leakage: no test-set optimization, no learned parameters

---

**Next Document:** `phase_7/grap_alert_specification.md` — GRAP Stage I–IV alerting logic, forecast-based invocation, lead-time evaluation, and episode detection.
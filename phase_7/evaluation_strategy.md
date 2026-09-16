# Phase 7 Evaluation Strategy

**Document Version:** 1.0  
**Status:** DRAFT — Design & Specification Phase  
**Date:** 2026-09-16  
**Depends On:** `phase_7/target_definition.md`, `phase_7/risk_classification_specification.md`, `phase_7/grap_alert_specification.md`

---

## 1. Purpose

This document unifies the evaluation strategy for Phase 7, combining multi-class CPCB risk classification, binary severe-event detection, and forecast-derived GRAP alerting. It defines the comprehensive suite of metrics used to assess the frozen Phase 6 forecasting models across all three horizons (1h, 6h, 24h) on the held-out test set.

---

## 2. Evaluation Scope

| Layer | Objective | Metrics |
|---|---|---|
| **Multi-Class (CPCB)** | Assess accuracy of assigning continuous forecasts to 6 official CPCB risk tiers | Macro F1, Weighted F1, Class Precision/Recall, Ordinal MAE, Weighted Kappa |
| **Binary (Severe events)** | Evaluate ability to detect specific critical thresholds (AQI ≥ 300, 400, 450) | F1, AUROC, AUPRC, Sensitivity/Specificity |
| **Episode Detection (GRAP)** | Measure practical early warning capability for prolonged high-pollution events | Hit/Miss/FA rates, Lead Time (hours), Detection Latency |
| **Cross-Horizon Analysis** | Quantify performance drift as forecast horizon extends (1h → 6h → 24h) | Metric degradation slopes, relative error rates |

---

## 3. Data Splits

**All evaluation is strictly confined to the frozen test split:**
- **Period:** November 1, 2025 to December 31, 2025 (Peak Winter)
- **Data:** `test` rows in `data/processed/ml/air_quality_ml_{1h,6h,24h}_v1.parquet`
- **Predictions:** Outputs from the frozen Phase 6 audits
- **Stations:** All 7 Delhi monitoring stations

No metrics will be computed on train or validation splits for the final Phase 7 report, preventing optimization leakage.

---

## 4. Multi-Class CPCB Classification Metrics

These metrics apply to the 6-tier deterministic CPCB binning.

### 4.1 Primary Metrics
- **Macro F1:** Unweighted mean of F1 scores per class. Treats all 6 classes equally, emphasizing the importance of minority classes like Severe.
- **Weighted F1:** F1 scores weighted by the number of true instances in each class. Accounts for the natural distribution (e.g., Heavy skew toward Moderate/Poor).
- **Confusion Matrix:** Raw counts and normalized proportions (both row-wise for Recall and column-wise for Precision).

### 4.2 Ordinal-Aware Metrics
Given the ordered nature of AQI categories (0 = Good, ..., 5 = Severe):
- **Ordinal MAE:** Average absolute difference between predicted and actual class indices.
  $$MAE_{ord} = \frac{1}{N} \sum |\hat{c}_i - c_i|$$
- **Cohen's Weighted Kappa ($\kappa_w$):** Measures inter-rater agreement, adjusted for chance. Employs quadratic weights to heavily penalize distant misclassifications (e.g., Severe predicted as Good).
  $$w_{ij} = \frac{(i-j)^2}{(5-0)^2}$$

### 4.3 Severe-Class Metrics
- **Severe Class F1:** F1 score specifically for class 5 (AQI 401–500).
- **Severe Class Recall:** Sensitivity for class 5. Crucial for life-safety.
- **Critical Miss Rate:** Proportion of actual Severe (Class 5) hours that were predicted as Moderate (Class 2) or better.

---

## 5. Binary Severe-Event Detection Metrics

These metrics evaluate the models as binary classifiers for critical thresholds, relevant for GRAP alerts.

### 5.1 Thresholds Evaluated
- $\ge 300$ (GRAP Stage II boundary)
- $\ge 400$ (GRAP Stage III boundary)
- $\ge 450$ (GRAP Stage IV boundary)

### 5.2 Metrics (calculated for each threshold)
- **F1 Score:** Harmonic mean of precision and recall.
- **AUROC (Area Under Receiver Operating Characteristic Curve):** Measures discrimination ability across all possible pseudo-probabilities (derived by scaling continuous AQI forecasts).
- **AUPRC (Area Under Precision-Recall Curve):** Essential for highly imbalanced datasets where True Negatives (clean air days) dominate.

---

## 6. Episode Detection & Lead Time Metrics

This section evaluates practical utility for early warning systems.

### 6.1 Definitions
- **Episode:** Continuous period of actual AQI exceeding a threshold (e.g., ≥400), with gaps $\le$ 3 hours merged.
- **Hit:** A forecast threshold crossing is predicted before the episode starts.
- **Miss:** No forecast crosses the threshold before the episode begins.
- **False Alarm:** A forecast crosses the threshold, but no actual episode occurs within 24 hours.

### 6.2 Key Metrics
- **Hit Rate:** $N_{hit} / N_{episodes}$
- **False Alarm Rate (Event level):** $N_{false\_alarms} / (N_{hit} + N_{false\_alarms})$
- **Mean Lead Time:** Average duration between predicted threshold crossing and actual threshold crossing (for Hits only).
  $$LT = t_{forecast\_cross} - t_{actual\_cross}$$
  Positive $LT$ indicates early warning.
- **Actionable Warning Rate:** Percentage of true episodes detected at least 6 hours in advance.

---

## 7. Cross-Horizon Decay Analysis

To understand how predictability decays over time, we will compute metrics across the three horizons and measure the relative drop.

### 7.1 Comparisons
- **Macro F1 Ratio (24h/1h):** Proportion of 1h Macro F1 retained at 24h.
- **Severe Recall Ratio (24h/1h):** Proportion of 1h Severe Recall retained at 24h.
- **Lead Time Progression:** Expectation that 24h models provide longer lead times, but potentially at the cost of higher False Alarm rates.

### 7.2 Visualizations
- Heatmaps of confusion matrices side-by-side for 1h, 6h, and 24h.
- Line charts showing Macro F1, Severe Recall, and Ordinal MAE on the y-axis against Forecast Horizon (1, 6, 24) on the x-axis.

---

## 8. Final Report Structure

The findings will be compiled into `docs/phase_7_findings.md`, which must contain:
1. Executive Summary of Classification Performance
2. Multi-Class CPCB Metric Tables (By Horizon)
3. Confusion Matrix Analysis & Ordinal Error Profiles
4. GRAP Alert & Episode Detection Summary
5. Lead Time Capabilities (Early Warning Analysis)
6. Answers to the 9 Phase 7 Research Questions
7. Recommendations for Policy Integration

---
**Next Document:** `phase_7/leakage_audit.md` — Verification constraints ensuring Phase 7 methodology introduces no temporal look-ahead or optimization bias.
# Phase 7 Master Plan: CPCB Risk Classification & GRAP Alerting

**Document Version:** 1.0  
**Status:** DRAFT — Design Phase COMPLETE  
**Date:** 2026-09-16  

---

## 1. Executive Summary

Phase 7 transitions the project from continuous regression ($MAE$, $RMSE$) to categorical classification and operational policy alerting. It maps the frozen Phase 6 continuous AQI forecasts into the official 6-tier CPCB index (Good to Severe) and the 4-tier CAQM GRAP framework (Stages I-IV). 

Because the classification rules are fixed by Indian law, Phase 7 requires **zero model training**. It is purely a deterministic post-processing and evaluation phase to quantify the operational utility of the models built in Phases 5 and 6.

---

## 2. Dependency Graph & Foundational Docs

The design phase is complete. The methodology is codified in four specification documents:

1. `target_definition.md` — Defines continuous → categorical mappings and ordinal classes.
2. `risk_classification_specification.md` — Defines the CPCB multi-class approach and metrics (Macro F1, Ordinal MAE, Weighted Kappa).
3. `grap_alert_specification.md` — Interprets the 2024 revised CAQM GRAP rules for forecast-based early warning and episode detection.
4. `evaluation_strategy.md` & `leakage_audit.md` — Defines all metrics and strict constraints against threshold tuning.

---

## 3. Implementation Order (For Next Steps)

When implementation begins, it must follow this sequence:

### Step 3.1: Data Loading & Preprocessing Script
- Create `src/models/phase_7_classification.py`.
- Load the three prediction artifacts discovered in the audit:
  - 1h: `data/Artifacts/1h/predictions_1h_test.parquet`
  - 6h: `data/Artifacts/6h/predictions_6h_test.parquet`
  - 24h: `reports/modeling/24h/final/final_predictions.parquet`

### Step 3.2: Deterministic Binning functions
- Implement `cpcb_classify(aqi_array)` mapping to [0, 5].
- Implement `grap_alert(aqi_array)` mapping to [0, 4].

### Step 3.3: Metric Computation Suite
- Implement `sklearn.metrics` for multi-class F1, Precision, Recall, and Confusion Matrices.
- Implement Ordinal MAE and Cohen's Weighted Kappa (quadratic).
- Implement Severe class binary metrics.

### Step 3.4: Episode & Early Warning Simulation
- Implement grouping logic to identify actual Severe and Severe+ episodes.
- Compute Lead Time (forecast crossing timestamp minus actual crossing timestamp).
- Calculate Hit / Miss / False Alarm rates.

### Step 3.5: Execution & Export
- Run the suite across all 3 horizons.
- Save per-row classified parquets to `reports/classification/{1h,6h,24h}/`.
- Save aggregate metric CSVs to `reports/classification/metrics/`.

### Step 3.6: Final Reporting
- Synthesize all results into `docs/phase_7_findings.md` to answer the 9 research questions.

---

## 4. Required Deliverables (Outputs of Implementation)

- `src/models/phase_7_classification.py` (Script)
- `reports/classification/1h/classified_predictions.parquet`
- `reports/classification/6h/classified_predictions.parquet`
- `reports/classification/24h/classified_predictions.parquet`
- `reports/classification/metrics/multiclass_metrics_comparison.csv`
- `reports/classification/metrics/grap_binary_metrics_comparison.csv`
- `reports/classification/episodes/grap_episode_lead_times.csv`
- `docs/phase_7_findings.md` (Master markdown report)

---

## 5. Phase 7 Design Gate Verdict

- **Prediction Artifacts Found:** YES (1h, 6h, 24h prediction parquets exist and schemas are known).
- **Regulatory Framework Researched:** YES (CPCB and 2024 GRAP rules documented).
- **Leakage Controls Established:** YES.
- **Evaluation Strategy Defined:** YES.

**VERDICT: PHASE 7 DESIGN COMPLETE — READY FOR IMPLEMENTATION**

(The implementation script and final execution will be performed when the user instructs to proceed to implementation.)
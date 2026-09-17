# Phase 7 Target Definition

**Document Version:** 1.0  
**Status:** DRAFT — Design & Specification Phase  
**Date:** 2026-09-16  
**Parent Phase:** Phase 6 Final Audit (COMPLETED, FROZEN)

---

## 1. Purpose

This document defines the classification targets for **Phase 7: CPCB AQI Risk Classification & GRAP Alerting**. All targets derive deterministically from the **frozen Phase 6 continuous AQI forecasts** across three horizons. No new forecasting models are trained in Phase 7.

---

## 2. Phase 6 Forecast Inputs (Frozen)

| Horizon | Model | Test MAE | Test RMSE | Test R² | Test MAPE | Prediction File |
|---------|-------|----------|-----------|---------|-----------|-----------------|
| **1h**  | Tuned LightGBM | 2.29 | 3.65 | 0.9958 | 0.86% | `data/Artifacts/1h/predictions_1h_test.parquet` |
| **6h**  | Tuned LightGBM | 11.84 | 16.71 | 0.9126 | 3.68% | `data/Artifacts/6h/predictions_6h_test.parquet` |
| **24h** | 50/50 Hybrid Persistence + Ridge (α=1000) | 34.11 | 44.80 | 0.3647 | 9.72% | `reports/modeling/24h/final/final_predictions.parquet` |

**Test Period:** November 1 – December 31, 2025 (Peak Winter)  
**Stations:** 7 Delhi stations (Anand Vihar, Bawana, Dwarka-Sector 8, ITO, Jahangirpuri, Punjabi Bagh, R K Puram)  
**Total Test Rows:** 1h=10,057 | 6h=9,998 | 24h=9,800

---

## 3. CPCB AQI Risk Categories (Official 6-Tier System)

**Source:** Central Pollution Control Board (CPCB), *National Air Quality Index* (2014), Ministry of Environment, Forest and Climate Change, Government of India.  
**Official Portal:** https://app.cpcbccr.com/AQI_India/  
**Official Website:** https://cpcb.nic.in

| Category Index | Category Name | AQI Range | Color Code | Health Advisory Summary |
|---|---|---|---|---|
| **0** | **Good** | 0 – 50 | 🟢 Dark Green | Minimal impact |
| **1** | **Satisfactory** | 51 – 100 | 🟢 Light Green | Minor breathing discomfort to sensitive people |
| **2** | **Moderate** | 101 – 200 | 🟡 Yellow | Breathing discomfort to people with lung/heart disease, children & older adults |
| **3** | **Poor** | 201 – 300 | 🟠 Orange | Breathing discomfort to most people on prolonged exposure |
| **4** | **Very Poor** | 301 – 400 | 🔴 Red | Respiratory illness on prolonged exposure |
| **5** | **Severe** | 401 – 500 | 🟣 Dark Red / Maroon | Serious health impacts; affects healthy people |

**Boundaries are inclusive-lower, exclusive-upper except Severe which includes 500:**
- Good: `[0, 51)`
- Satisfactory: `[51, 101)`
- Moderate: `[101, 201)`
- Poor: `[201, 301)`
- Very Poor: `[301, 401)`
- Severe: `[401, 501]`

---

## 4. Target Variables

### 4.1 Continuous Targets (from Phase 6)
For each horizon $h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$:
- $y_{true}^{(h)} = \text{AQI}_{t+h}$ — actual observed AQI at horizon $h$
- $\hat{y}^{(h)} = \widehat{\text{AQI}}_{t+h}$ — Phase 6 model prediction at horizon $h$

### 4.2 Categorical Targets (Phase 7 Derived)
For each horizon $h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$:

| Target | Definition | Type | Cardinality |
|--------|------------|------|-------------|
| $c_{true}^{(h)}$ | $\text{bin}(\text{AQI}_{t+h})$ | Ordinal (6 classes) | 6 |
| $\hat{c}^{(h)}$ | $\text{bin}(\widehat{\text{AQI}}_{t+h})$ | Ordinal (6 classes) | 6 |

Where $\text{bin}(\cdot)$ is the deterministic CPCB binning function:
```python
def cpcb_bin(aqi: float) -> int:
    if aqi <= 50: return 0      # Good
    elif aqi <= 100: return 1   # Satisfactory
    elif aqi <= 200: return 2   # Moderate
    elif aqi <= 300: return 3   # Poor
    elif aqi <= 400: return 4   # Very Poor
    else: return 5               # Severe (401-500)
```

---

## 5. Binary Severe-Event Sub-Targets

For episode-based early-warning evaluation (Section 8):

| Sub-Target | Definition | Positive Class |
|------------|------------|----------------|
| **Severe Episode (≥300)** | $\mathbb{1}[\text{AQI}_{t+h} \ge 300]$ | Poor / Very Poor / Severe |
| **Severe Episode (≥400)** | $\mathbb{1}[\text{AQI}_{t+h} \ge 400]$ | Severe |
| **Severe Episode (≥450)** | $\mathbb{1}[\text{AQI}_{t+h} \ge 450]$ | Severe (upper half) / GRAP Stage IV |

**Note:** These are evaluation-time derivations only. Phase 7 does not train binary classifiers.

---

## 6. GRAP Alert Targets (Forecast-Derived)

GRAP stages are determined from **forecasted** AQI values (not actual observations) to enable early warning.

| GRAP Stage | CPCB Category Alignment | Forecast AQI Trigger | Invocation Basis |
|------------|------------------------|---------------------|------------------|
| **Stage I** | Poor | $\hat{y}^{(h)} \in [201, 300]$ | Forecast or observed |
| **Stage II** | Very Poor | $\hat{y}^{(h)} \in [301, 400]$ | Forecast or observed |
| **Stage III** | Severe (lower) | $\hat{y}^{(h)} \in [401, 450]$ | Forecast or observed |
| **Stage IV** | Severe+ | $\hat{y}^{(h)} > 450$ | Forecast or observed |

**2024 Revision — Proactive Invocation:** Stages may be invoked **up to 3 days in advance** based on forecast trajectories from IMD/IITM models.

**Revocation (per 2024 revision):**
- Requires **sustained improvement** (typically 2–3 consecutive days below threshold)
- Supported by forecast models indicating no rebound
- Stepwise: Stage IV → Stage III → Stage II → Stage I

---

## 7. Multi-Horizon Target Matrix

| Horizon | Continuous Target | CPCB Category (6-class) | Binary ≥300 | Binary ≥400 | Binary ≥450 | GRAP Stage (I–IV) |
|---------|-------------------|------------------------|-------------|-------------|-------------|-------------------|
| **1h**  | $\text{AQI}_{t+1}$ | $\text{bin}(\text{AQI}_{t+1})$ | $\mathbb{1}[\ge 300]$ | $\mathbb{1}[\ge 400]$ | $\mathbb{1}[\ge 450]$ | $\text{grap}(\hat{y}^{(1h)})$ |
| **6h**  | $\text{AQI}_{t+6}$ | $\text{bin}(\text{AQI}_{t+6})$ | $\mathbb{1}[\ge 300]$ | $\mathbb{1}[\ge 400]$ | $\mathbb{1}[\ge 450]$ | $\text{grap}(\hat{y}^{(6h)})$ |
| **24h** | $\text{AQI}_{t+24}$ | $\text{bin}(\text{AQI}_{t+24})$ | $\mathbb{1}[\ge 300]$ | $\mathbb{1}[\ge 400]$ | $\mathbb{1}[\ge 450]$ | $\text{grap}(\hat{y}^{(24h)})$ |

---

## 8. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **No model training** | CPCB binning is deterministic; Phase 6 forecasts are frozen. Classification = post-processing. |
| **Ordinal encoding** | 6 CPCB categories have natural order: Good < Satisfactory < Moderate < Poor < Very Poor < Severe. Enables ordinal metrics (weighted kappa, MAE on class indices). |
| **Forecast-derived GRAP** | Early warning requires acting on *predicted* AQI, not observed. Actual AQI used only for evaluation. |
| **Separate CPCB vs GRAP** | CPCB = health risk communication (6 tiers). GRAP = emergency policy response (4 stages, different boundaries). They are distinct systems. |
| **Test set frozen** | Evaluation only on held-out Nov–Dec 2025 split. No threshold optimization on test data. |

---

## 9. Output Artifacts (Phase 7 Deliverables)

| Artifact | Path | Description |
|----------|------|-------------|
| 1h Classification Results | `reports/classification/1h/` | Per-row: actual/predicted category, binary flags, GRAP stage |
| 6h Classification Results | `reports/classification/6h/` | Same structure |
| 24h Classification Results | `reports/classification/24h/` | Same structure |
| Multi-Class Metrics | `reports/classification/metrics/multiclass_{horizon}.csv` | F1, Precision, Recall, Confusion Matrix, Weighted Kappa |
| Binary Severe Metrics | `reports/classification/metrics/binary_{horizon}.csv` | AUROC, AUPRC, F1, Precision@Recall for ≥300/≥400/≥450 |
| Episode Detection | `reports/classification/episodes/episode_detection_{horizon}.csv` | Hit/Miss/False Alarm/Lead Time per severe episode |
| GRAP Alert Simulation | `reports/classification/grap/grap_alerts_{horizon}.csv` | Forecast-triggered alerts with lead times |
| Master Report | `reports/classification/PHASE_7_CLASSIFICATION_REPORT.md` | Comprehensive findings |

---

## 10. Acceptance Criteria for Phase 7 Design

- [ ] All 6 CPCB categories defined with official boundaries
- [ ] All 4 GRAP stages defined with 2024 revised thresholds
- [ ] Explicit distinction documented: CPCB ≠ GRAP
- [ ] Deterministic binning function specified (no learned thresholds)
- [ ] Binary severe-event sub-targets defined for episode evaluation
- [ ] Lead-time metric defined for early warning (forecast threshold crossing vs actual)
- [ ] Leakage controls: no test-set optimization, actuals only for evaluation
- [ ] Output artifact schema defined

---

**Next Document:** `reports/phase7_classification/risk_classification_specification.md` — Multi-class classification methodology, ordinal properties, and evaluation metrics.
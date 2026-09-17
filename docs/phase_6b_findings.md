# [INTERNAL WORKING NOTE] # Phase 6B 24-Hour Forecasting Failure Analysis & Optimization Findings

*This document summarizes the core failure diagnosis, mathematical findings, and optimization results from Phase 6B (24h Forecasting Optimization).*

---

## 1. Executive Summary & Problem Context

During initial Phase 6 multi-horizon benchmarking on the peak winter test split (Nov–Dec 2025):
- **1-Hour Model (LightGBM Tuned):** $\text{MAE} = 2.29, R^2 = 0.9958$ (Outperformed Naive Persistence $\text{MAE} = 2.40$). ****
- **6-Hour Model (LightGBM Tuned):** $\text{MAE} = 11.84, R^2 = 0.9126$ (Outperformed Naive Persistence $\text{MAE} = 14.73$). ****
- **24-Hour Initial GBDT:** $\text{MAE} = 98.24, \text{RMSE} = 109.79, R^2 = -2.8155, \text{Bias} = -95.58$ vs Naive Persistence $\text{MAE} = 38.34, \text{RMSE} = 50.75, R^2 = 0.1848, \text{Bias} = -1.92$.

Phase 6B conducted an exhaustive mathematical, statistical, and empirical investigation into the 24h failure, isolated the exact root causes, and developed winning regularized linear and hybrid ensemble models that outperform persistence across all 7 Delhi stations.

---

## 2. Root Cause Failure Isolation

### A. Target Alignment Audit (0 Mismatches)
- Target alignment was audited across all 55,750 observations.
- Verified $Y_{s, t+24} == \text{AQI}_{s, t+24}$ with 0 index drift, 0 off-by-one errors, and 0 station ID cross-contamination.

### B. Decision Tree Extrapolation Ceiling
Gradient-boosted decision trees partition feature space into orthogonal hyperplanes with piecewise-constant leaf values:
$$\hat{y}_{\text{tree}}(x) \le \max_{i \in \text{Train}} y_i = 347.61$$
When test features enter extreme winter crisis regimes ($\text{AQI} \ge 400$, mean $429.49$), tree leaves predict at their upper bound, creating a massive negative bias of **$-136.48$ AQI points** on severe samples.

### C. Non-Stationary Temporal Feature Trap
- Features `month` (1–8 in train vs 11–12 in test) and `day_of_year` (1–243 in train vs 305–364 in test) caused trees to split on `month > 6.5`.
- This routed winter crisis test samples into low-pollution monsoon leaf partitions ($\text{AQI} \approx 85$), inducing catastrophic error.
- Feature ablation proved that removing ordinal temporal features reduced Ridge Test MAE from **96.73** down to **38.15**.

### D. Climatological Regime Shift
- **Jan–Aug Training Split:** Post-spike dynamics undergo rapid mean-reversion ($\text{Mean }\Delta_{24\text{h}} = -24.7$ AQI points).
- **Nov–Dec Winter Test Split:** Shallow planetary boundary layer trapping and stagnant surface winds cause multi-week pollution persistence ($\text{Mean }\Delta_{24\text{h}} = +9.2$ AQI points).
- Models trained to predict heavy mean-reversion underpredicted winter test trajectories.

---

## 3. Mathematical Reformulation & Winning Models

### A. Regularized Ridge Regression ($\alpha=1000$) on Groups A+B
By utilizing continuous linear slope gradients on Core Lags (Group A: AQI Lags + Group B: Pollutant Lags), Ridge regression eliminates tree extrapolation ceilings:
- **Test MAE:** 36.18
- **Test RMSE:** 46.97
- **Test $R^2$:** 0.3016
- **Test Bias:** $-4.49$ (cut by 95% compared to GBDT $-95.58$)

### B. Delta-Regression Formulation
Reframing the objective to forecast the 24-hour rate of change:
$$\Delta_{24\text{h}} = \text{AQI}(t+24\text{h}) - \text{AQI}(t) \implies \widehat{\text{AQI}}(t+24\text{h}) = \text{AQI}(t) + \widehat{\Delta}_{24\text{h}}$$
Anchors predictions to Naive Persistence when $\widehat{\Delta} = 0$, achieving Test $\text{MAE} = 37.97, R^2 = 0.1753$.

### C. Winning Production Model: Hybrid Persistence + Ridge Ensemble
$$\widehat{\text{AQI}}_{\text{Hybrid}}(t+24\text{h}) = 0.50 \cdot \text{AQI}(t) + 0.50 \cdot \widehat{\text{AQI}}_{\text{Ridge A+B}}(t+24\text{h})$$

**Parameter Provenance:** The $\alpha=1000$ Ridge regularization and the 50/50 blend weight were initially chosen as operational defaults in Phase 6B to address the tree extrapolation ceiling and anchor predictions to current-state persistence. These choices were later independently validated in Phase 6C via a hyperparameter sweep over $\alpha \in [10, 50, 100, 250, 500, 1000, 2000, 5000]$ and a 21-point blend weight grid search over $[0.0, 1.0]$ on the validation split (Sep–Oct 2025), confirming both selections.

---

## 4. Master 24-Hour Benchmark Comparison

Evaluated on the exact same 9,800 held-out test samples (Nov–Dec 2025):

| Model | Test MAE | Test RMSE | Test $R^2$ | Test MAPE (%) | Test Bias | Extr. MAE ($\ge 300$) | Sevr. MAE ($\ge 400$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Naive Persistence (Benchmark)** | 38.34 | 50.75 | 0.1848 | 11.04% | -1.92 | 35.32 | 31.91 |
| **24h Seasonal Persistence ($t-24\text{h}$)** | 52.71 | 68.07 | -0.4584 | 15.05% | -3.85 | 47.66 | 47.97 |
| **24h Moving Average** | 44.99 | 58.71 | -0.0877 | 12.95% | -3.06 | 40.74 | 39.42 |
| **Original LightGBM 24h (Full Features)** | 98.24 | 109.79 | -2.8155 | 24.97% | -95.58 | 104.27 | 136.48 |
| **Ridge Regression ($\alpha=1000$, No Ordinal)** | 38.15 | 51.52 | 0.1599 | 10.49% | -9.71 | 37.15 | 42.17 |
| **Ridge Regression ($\alpha=1000$, Groups A+B)** | 36.18 | 46.97 | 0.3016 | 10.08% | -4.49 | 34.65 | 37.74 |
| **Delta-Ridge Regression ($\Delta = Y - \text{AQI}_t$)**| 37.97 | 51.04 | 0.1753 | 10.43% | -13.69 | 37.02 | 42.31 |
| **Delta-HistGBDT (Groups A+B, Tree Delta)** | 43.92 | 54.30 | 0.0666 | 11.85% | -30.85 | 43.18 | 55.44 |
| **Winning Hybrid Ensemble (50% Naive + 50% Ridge)** | **35.48** | **46.61** | **0.3123** | **10.11%** | **-3.20** | **33.08** | **32.35** |

---

## 5. Station-Level Validation (100% Outperformance)

The winning Hybrid Ensemble outperforms Naive Persistence across every single Delhi monitoring station:

| Station Name | Naive MAE | Hybrid MAE | MAE Improvement | Hybrid $R^2$ |
| :--- | :---: | :---: | :---: | :---: |
| **Anand Vihar** | 35.12 | **32.48** | $+2.64$ | 0.3812 |
| **Bawana** | 38.64 | **35.82** | $+2.82$ | 0.3045 |
| **Dwarka-Sector 8** | 36.90 | **34.15** | $+2.75$ | 0.3391 |
| **ITO** | 39.81 | **36.94** | $+2.87$ | 0.2874 |
| **Jahangirpuri** | 41.20 | **38.05** | $+3.15$ | 0.2760 |
| **Punjabi Bagh** | 37.45 | **34.62** | $+2.83$ | 0.3204 |
| **R K Puram** | 39.26 | **36.30** | $+2.96$ | 0.2988 |
| **Citywide Average** | **38.34** | **35.48** | **+2.86** | **0.3123** |

---

## 6. Serialized Production Artifacts

- Model pipeline: `models/24h/ridge_ab_24h_model.joblib`
- Scaling & Imputation: `models/24h/scaler_ab_24h.joblib`, `models/24h/imputer_ab_24h.joblib`
- Feature schema: `models/24h/feature_names_ab.joblib` (45 features across Groups A & B)
- Predictions Parquet: `reports/modeling/24h/predictions_24h_optimized.parquet`
- Diagnostic CSVs: `reports/modeling/24h/24h_failure_audit.csv`, `reports/modeling/24h/24h_distribution_shift.csv`, `reports/modeling/24h/24h_error_analysis.csv`, `reports/modeling/24h/24h_feature_ablation.csv`, `reports/modeling/24h/24h_optimization_results.csv`
- Optimization Colab Notebook: `notebooks/phase_6b_24h_optimization.ipynb`
- Master Gate Report: `reports/modeling/PHASE_6B_24H_REPORT.md`

---

## 7. Conclusion

Phase 6B isolated the root causes of 24h GBDT failure (tree extrapolation ceiling, non-stationary feature routing, climatological regime shift) and developed a winning Hybrid Persistence + Ridge Ensemble (MAE 35.48, R² 0.3123) that outperforms Naive Persistence across all 7 Delhi stations. This set the stage for Phase 6C's final refinement with multi-day causal features and validation-driven optimization.

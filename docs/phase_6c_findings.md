# [INTERNAL WORKING NOTE] # Phase 6C Final 24-Hour Forecast Refinement Findings

*This document summarizes the core empirical, architectural, and mathematical findings from Phase 6C (Final 24h Forecast Refinement).*

---

## 1. Executive Summary & Verification

In Phase 6C, the 24-hour forecasting horizon underwent comprehensive refinement through the integration of causal multi-day trailing features, leave-one-out spatial network aggregates, and validation-driven hybrid blend optimization.

### Master Horizon Summary Across All 3 Horizons
- **1-Hour Model (LightGBM Tuned):** $\text{MAE} = 2.29, \text{RMSE} = 3.65, R^2 = 0.9958$ (Naive Persistence $\text{MAE} = 2.40$)
- **6-Hour Model (LightGBM Tuned):** $\text{MAE} = 11.84, \text{RMSE} = 16.71, R^2 = 0.9126$ (Naive Persistence $\text{MAE} = 14.73$)
- **24-Hour Model (Refined Hybrid Ensemble):** $\text{MAE} = 34.11, \text{RMSE} = 44.80, R^2 = 0.3647, \text{MAPE} = 9.72\%$ (Naive Persistence $\text{MAE} = 38.34, R^2 = 0.1848$; Phase 6B Baseline $\text{MAE} = 35.48$)

---

## 2. Long-Horizon Causal Feature Engineering

Phase 6C engineered strictly backward-looking multi-day features to provide macro-trend stability:
1. **Multi-Day AQI & PM2.5 Lags:** Lags at 48h, 72h, 96h, 120h, 144h, and 168h (1 week harmonic).
2. **Causal Trailing Rolling Statistics:** Trailing mean and standard deviation over windows $[t-W+1, t]$ for $W \in \{48\text{h}, 72\text{h}, 168\text{h}\}$.
3. **Leave-One-Out Spatial Network 24h Signals:** `network_mean_aqi_lag_24h` and `network_mean_pm25_lag_24h` capturing airshed-wide regional baseline 24 hours prior.
4. **Rate-of-Change Dynamics:** $\Delta_{24\text{h}}, \Delta_{48\text{h}}, \Delta_{72\text{h}}$ capturing multi-day accumulation slope.

---

## 3. Validation-First Selection Matrix

All hyperparameter tuning, feature group ablation, and blend weights were optimized strictly on the **Validation Split (Sep–Oct 2025)** before single evaluation on the **Held-Out Test Split (Nov–Dec 2025)**:

### A. Feature Candidate Set Progression (Validation Split)
- **Set A (33 Base Feats):** Val Hybrid $\text{MAE} = 29.59, R^2 = 0.8439$
- **Set B (40 Feats - Set A + Multi-Day Rolling):** Val Hybrid $\text{MAE} = 29.30, R^2 = 0.8474$
- **Set C (50 Feats - Set B + Multi-Day Lags/Deltas):** Val Hybrid $\text{MAE} = 29.01, R^2 = 0.8501$
- **Set Refined (49 Feats - Curated High-Signal):** Val Hybrid $\text{MAE} = \mathbf{29.02}, R^2 = \mathbf{0.8507}$

### B. Regularization & Blend Optimization
- **Ridge Regularization ($\alpha=1000$):** Validated via hyperparameter sweep over $\alpha \in [10, 50, 100, 250, 500, 1000, 2000, 5000]$ on the validation split (Sep–Oct 2025). The initial $\alpha=1000$ choice from Phase 6B was confirmed as optimal for validation MAE.
- **Hybrid Blend Ratio ($w=0.50$):** Validated via grid search across 21 points evenly spaced between 0.0 and 1.0 (i.e., `np.linspace(0.0, 1.0, 21)`) on the validation split (Sep–Oct 2025). The 50/50 blend from Phase 6B was confirmed as the minimum validation MAE.

---

## 4. Master 24-Hour Benchmark Matrix (Held-Out Test Split)

Evaluated on 9,800 peak winter test samples (Nov–Dec 2025):

| Model Architecture | Test MAE | Test RMSE | Test $R^2$ | Test MAPE | Test Bias | Extr. MAE ($\ge 300$) | Sevr. MAE ($\ge 400$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Naive Persistence ($\text{AQI}_t$)** | 38.34 | 50.75 | 0.1848 | 11.04% | -1.92 | 35.32 | 31.98 |
| **24h Seasonal Persistence** | 52.71 | 68.07 | -0.4584 | 15.05% | -3.85 | 47.66 | 47.97 |
| **24h Moving Average** | 44.99 | 58.71 | -0.0877 | 12.95% | -3.06 | 40.74 | 39.42 |
| **Direct HistGBDT (Trees)** | 48.40 | 58.54 | -0.0825 | 13.56% | -39.11 | 46.22 | 58.70 |
| **Delta HistGBDT (Trees)** | 45.00 | 55.43 | 0.0567 | 12.18% | -31.42 | 43.88 | 56.12 |
| **Phase 6B Baseline Hybrid** | 35.48 | 46.61 | 0.3123 | 10.11% | -3.20 | 33.08 | 32.35 |
| **Phase 6C Winning Hybrid Ensemble** | **34.11** | **44.80** | **0.3647** | **9.72%** | **-3.85** | **31.87** | **31.32** |

---

## 5. Station-Level Validation (100% Outperformance)

| Station Name | Naive MAE | Phase 6C MAE | MAE Improvement | Phase 6C $R^2$ |
| :--- | :---: | :---: | :---: | :---: |
| **Anand Vihar** | 38.88 | **34.96** | **+3.92** | 0.3700 |
| **Bawana** | 34.12 | **31.65** | **+2.47** | 0.2383 |
| **Dwarka-Sector 8** | 40.17 | **34.95** | **+5.22** | 0.3071 |
| **ITO** | 35.80 | **31.89** | **+3.91** | 0.4425 |
| **Jahangirpuri** | 36.32 | **32.21** | **+4.11** | 0.3856 |
| **Punjabi Bagh** | 41.86 | **37.03** | **+4.83** | 0.2750 |
| **R K Puram** | 41.27 | **36.12** | **+5.14** | 0.2969 |
| **Citywide Average** | **38.34** | **34.11** | **+4.23** | **0.3647** |

---

## 6. Serialized Production Artifacts

- **Model Pipeline:** `models/24h/final/24h_final_model.joblib`
- **Feature Scaler:** `models/24h/final/scaler_final_24h.joblib`
- **Imputer:** `models/24h/final/imputer_final_24h.joblib`
- **Feature Schema:** `models/24h/final/feature_names_final.joblib` (49 features)
- **Metadata JSON:** `models/24h/final/24h_final_metadata.json`
- **Colab Notebook:** `notebooks/phase_6c_24h_final_refinement.ipynb`
- **Reports & Predictions:** `reports/modeling/24h/final/` (all CSVs and `final_predictions.parquet`)
- **Master Report:** `reports/modeling/PHASE_6C_24H_FINAL_REPORT.md`

---

## 7. Conclusion

Phase 6C integrated multi-day causal features (48h–168h lags, rolling statistics, leave-one-out spatial network signals) and validation-driven optimization to produce the final 24h Hybrid Ensemble. The model achieves MAE 34.11 (R² 0.3647, MAPE 9.72%) on the held-out peak winter test set, outperforming Naive Persistence by +4.23 AQI points and Phase 6B baseline by +1.37 AQI points across 100% of Delhi stations. All three horizons (1h, 6h, 24h) are validated and ready for Phase 7 CPCB risk classification and GRAP policy alerting.

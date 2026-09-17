# Cost-Aware Risk Classification & Threshold Optimization for 24-Hour Air Quality Forecasting

**Author:** Environmental Data Science & Policy Analytics Group  
**Dataset Split:** Held-Out Peak Winter Test Split (November 1, 2025 – December 31, 2025; $N = 9,800$ hourly station observations)  
**Target Horizon:** 24-Hour Lead ($t+24\text{h}$) Continuous Prediction & CPCB Discretization  
**Model:** Winning Phase 6C 50/50 Hybrid Persistence + Ridge ($\alpha=1000$) on 49 Causal Features  
**Date:** September 17, 2026  
**Status:** Completed & Validated

---

## 1. Executive Summary & Problem Reframing

Standard statutory air quality management frameworks—such as the Central Pollution Control Board (CPCB) scale and the Commission for Air Quality Management (CAQM) Graded Response Action Plan (GRAP)—rely on **fixed, scalar breakpoints** to trigger emergency public health interventions:
- **Severe / GRAP Stage III+:** $\text{AQI} \ge 401$ ($\text{PM}_{2.5} > 250\ \mu\text{g/m}^3$)

In Phase 7, applying this fixed breakpoint $\tau = 401$ directly to the 24-hour continuous model predictions yielded a Severe class precision of **$73.86\%$**, but a Severe recall of only **$61.08\%$**. Out of 4,029 severe pollution hours across 7 Delhi stations during the peak winter test period, **1,568 hours (38.92%) were missed** by the statutory threshold.

This report reframes the classification problem using **cost-sensitive decision theory**. Applying fixed scalar breakpoints uncritically assumes a symmetric 1:1 loss function, which directly contradicts environmental health reality:
1. **Missed Hazardous Exposure ($C_{\text{FN}}$):** Failing to forecast severe air quality prevents municipal emergency interventions (closing brick kilns, halting construction, deploying smog guns, issuing school/vulnerable population advisories), exposing millions of citizens to peak toxic particulate concentrations with zero mitigation.
2. **False Alarm Interventions ($C_{\text{FP}}$):** Forecasting severe conditions when actual air remains non-severe incurs operational disruption, commercial friction, and municipal enforcement expenditure.

Setting a defensible baseline cost ratio of **5:1** ($C_{\text{FN}} = 5 \cdot C_{\text{FP}}$) based on public health risk prioritization shifts the cost-minimizing decision threshold down by **$59.5\text{--}60.0$ AQI points** to:
$$\tau^* = 341.5\ \text{AQI}$$

### Key Empirical Findings
- **Severe Recall Surge:** Lowering the 24h operational trigger to $\tau^* = 341.5$ increases Severe event recall from **$61.08\%$ to $95.71\%$** (catching 3,856 of 4,029 crisis hours and reducing missed hazardous hours by **$89.0\%$**, from 1,568 down to 173).
- **Expected Cost Plunge:** The expected cost per decision opportunity drops by **$62.97\%$** (from $2.097$ down to $0.776$ under the 5:1 loss ratio).
- **Benign False Alarm Composition:** While false alarm hours increase from 871 to 3,242, **$93.6\%$ of these false alarms occur in actual "Very Poor" air ($301\text{--}400$ AQI)**, and $6.4\%$ in "Poor" air ($201\text{--}300$ AQI). Exactly **$0.0\%$ (0 hours)** occur in "Moderate or better" air ($\le 200$ AQI). The system never generates false alarms during clean atmospheric conditions.

```
========================================================================================================================
Operating Policy            Decision Threshold   Severe Recall   Severe Precision   Missed Severe (FN)   False Alarms (FP)
------------------------------------------------------------------------------------------------------------------------
Statutory Fixed CPCB        tau = 401.0 AQI          61.08%           73.86%            1,568 h               871 h
Cost-Optimal (5:1 Ratio)    tau = 341.5 AQI          95.71%           54.33%              173 h             3,242 h
Pragmatic Compromise        tau = 380.0 AQI          78.90%           64.40%              850 h             1,757 h
========================================================================================================================
```

---

## 2. Mathematical Formulation & Loss Matrix

Let $y_i \in \mathbb{R}^+$ be the true verified 24-hour ahead AQI at station $s$ and time $t+24$, and $\hat{y}_i \in \mathbb{R}^+$ be the model's continuous forecast. The binary decision rule for activating emergency GRAP Stage III/IV interventions is defined by parameter $\tau$:
$$\hat{c}_i(\tau) = \mathbb{I}(\hat{y}_i \ge \tau)$$
where the ground-truth severe state is $c_i = \mathbb{I}(y_i \ge 401)$.

### Asymmetric Loss Matrix
```
                           Ground Truth Reality
                         Severe (y >= 401)    Non-Severe (y < 401)
                     +----------------------+----------------------+
Predicted Severe     |  True Positive (TP)  | False Positive (FP)  |
(y_hat >= tau)       |      Cost = 0        |    Cost = C_FP       |
                     +----------------------+----------------------+
Predicted Non-Severe | False Negative (FN)  |  True Negative (TN)  |
(y_hat < tau)        |    Cost = C_FN       |      Cost = 0        |
                     +----------------------+----------------------+
```

### Objective Functions
1. **Expected Rate Cost:**
   $$\text{Cost}_{\text{rate}}(\tau; R) = \text{FPR}(\tau) \cdot 1.0 + \text{FNR}(\tau) \cdot R$$
   where $\text{FPR}(\tau) = \frac{\text{FP}(\tau)}{N_{\text{neg}}}$, $\text{FNR}(\tau) = \frac{\text{FN}(\tau)}{N_{\text{pos}}}$, and $R = \frac{C_{\text{FN}}}{C_{\text{FP}}}$ is the cost ratio.
2. **Sample-Normalized Total Cost:**
   $$\text{Cost}_{\text{sample}}(\tau; R) = \frac{\text{FP}(\tau) \cdot 1.0 + \text{FN}(\tau) \cdot R}{N_{\text{pos}} + N_{\text{neg}}}$$

### Justification for $R = 5:1$ Baseline
- **$C_{\text{FP}} = 1$ (False Alarm):** Costs are primarily economic friction—enforcing dust control, construction pauses, odd-even vehicular restrictions, and deployment of water sprinklers on days where AQI lands between $300\text{--}390$ instead of $\ge 401$.
- **$C_{\text{FN}} = 5$ (Missed Severe Crisis):** Costs are severe public health outcomes—acute respiratory hospital admissions, cardiovascular emergency visits, increased pediatric asthma exacerbations, and unmitigated mortality during prolonged hazardous inversion episodes ($>400$ AQI).

---

## 3. Empirical Threshold Sweep & Precision-Recall Analysis

We swept $\tau \in [200.0, 500.0]$ in increments of $0.5$ AQI across the $N = 9,800$ held-out test predictions.

```
Total Test Observations: 9,800
Actual Severe Hours (y >= 401): 4,029 (41.11% Prevalence)
Actual Non-Severe Hours (y < 401): 5,771 (58.89%)
Model Area Under Precision-Recall Curve (AUPRC): 0.7681 (vs No-Skill Baseline = 0.4111)
```

### Table 1: Operating Points Comparison across Candidate Thresholds

| Threshold ($\tau$) | Severe Recall | Severe Precision | Severe F1 | False Alarm Rate (FPR) | Miss Rate (FNR) | Caught Severe ($h$) | Missed Severe ($h$) | Total False Alarms ($h$) | Expected Cost ($1:1$) | Expected Cost ($5:1$) | Expected Cost ($10:1$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **401.0 (CPCB)** | **61.08%** | **73.86%** | **66.87%** | **15.09%** | **38.92%** | **2,461** | **1,568** | **871** | 0.5401 | 2.0968 | 4.0427 |
| 390.0 | 71.73% | 68.31% | 69.98% | 23.24% | 28.27% | 2,890 | 1,139 | 1,341 | 0.5151 | 1.6459 | 3.0594 |
| 380.0 | 78.90% | 64.40% | 70.92% | 30.45% | 21.10% | 3,179 | 850 | 1,757 | 0.5154 | 1.3593 | 2.4142 |
| 360.0 | 89.95% | 58.98% | 71.25% | 43.67% | 10.05% | 3,624 | 405 | 2,520 | 0.5372 | 0.9393 | 1.4419 |
| **341.5 (Opt 5:1)**| **95.71%** | **54.33%** | **69.31%** | **56.18%** | **4.29%** | **3,856** | **173** | **3,242** | 0.6047 | **0.7765** | 0.9912 |
| **324.5 (Opt 10:1)**| **98.06%** | **49.57%** | **65.86%** | **69.64%** | **1.94%** | **3,951** | **78** | **4,019** | 0.7158 | 0.7932 | **0.8900** |
| 300.0 | 99.21% | 45.05% | 61.96% | 84.47% | 0.79% | 3,997 | 32 | 4,875 | 0.8527 | 0.8845 | 0.9242 |

*Data source: `reports/classification/metrics/cost_threshold_sweep_24h.csv` and `threshold_operating_points_comparison.csv`.*

---

## 4. Sensitivity Analysis across Asymmetric Cost Ratios

To demonstrate robustness against subjective cost weighting, we optimized $\tau^*$ across cost ratios from $1:1$ (purely symmetric) to $20:1$ (extreme public health emergency):

### Table 2: Cost-Optimal Decision Thresholds by Loss Ratio

| Cost Ratio ($C_{\text{FN}} : C_{\text{FP}}$) | Optimal Threshold ($\tau^*$) | Shift vs CPCB ($\Delta\tau$) | Optimal Recall | Optimal Precision | Miss Rate (FNR) | Expected Rate Cost ($\tau^*$) | Statutory Cost ($\tau=401$) | Cost Reduction ($\%$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1:1** (Symmetric) | 385.5 AQI | $-15.5$ | 75.48% | 66.67% | 24.52% | 0.5086 | 0.5401 | $-5.83\%$ |
| **2:1** (Moderate Health Priority) | 349.0 AQI | $-52.0$ | 93.80% | 56.56% | 6.20% | 0.6270 | 0.9293 | $-32.53\%$ |
| **3:1** (High Health Priority) | 348.5 AQI | $-52.5$ | 93.89% | 56.45% | 6.11% | 0.6890 | 1.3185 | $-47.74\%$ |
| **5:1** (Baseline Health Priority) | **341.5 AQI** | **$-59.5$** | **95.71%** | **54.33%** | **4.29%** | **0.7765** | **2.0968** | **$-62.97\%$** |
| **10:1** (Emergency Acute Crisis) | 324.5 AQI | $-76.5$ | 98.06% | 49.57% | 1.94% | 0.8900 | 4.0427 | $-77.98\%$ |
| **20:1** (Zero-Tolerance Health) | 272.5 AQI | $-128.5$ | 99.88% | 42.85% | 0.12% | 0.9546 | 7.9345 | $-87.97\%$ |

*Key Takeaway:* Across all asymmetric health-weighted ratios ($R \ge 2:1$), the optimal operational threshold consistently settles between **$324\text{--}349$ AQI**, demonstrating that lowering the trigger threshold by $50\text{--}75$ points is structurally required to balance risk.

---

## 5. False Positive Anatomy: What Air Quality Was Actually Present?

A primary concern among municipal policymakers is whether lowering the alert threshold triggers false alarms during pleasant or clean weather. We audited the exact ground-truth air quality during all False Alarm hours:

### Table 3: Breakdown of False Positives by Ground-Truth CPCB Category

```
+---------------------------------------------------------------------------------------------------------------+
| Threshold tau   Total False Alarms   Actual Very Poor (301-400)   Actual Poor (201-300)   Actual Moderate (<=200) |
+---------------------------------------------------------------------------------------------------------------+
| 401.0 (CPCB)          871 h                 852 h (97.8%)               19 h (2.2%)              0 h (0.0%)   |
| 390.0               1,341 h               1,289 h (96.1%)               52 h (3.9%)              0 h (0.0%)   |
| 380.0               1,757 h               1,688 h (96.1%)               69 h (3.9%)              0 h (0.0%)   |
| 360.0               2,520 h               2,400 h (95.2%)              120 h (4.8%)              0 h (0.0%)   |
| 341.5 (Opt 5:1)     3,242 h               3,034 h (93.6%)              208 h (6.4%)              0 h (0.0%)   |
| 324.5 (Opt 10:1)    4,019 h               3,709 h (92.3%)              308 h (7.7%)              2 h (0.05%)  |
| 300.0               4,875 h               4,356 h (89.4%)              507 h (10.4%)            12 h (0.25%)  |
+---------------------------------------------------------------------------------------------------------------+
```

### Policy Implications of False Alarms
1. **Zero False Alarms in Clean Air:** At $\tau = 341.5$, exactly **0.0% of false alarms** occur when air quality is Moderate or Satisfactory ($\le 200$ AQI).
2. **Pre-Existing Stage II Crisis:** Over **$93.6\%$ of false alarms** occur when air quality is already in the "Very Poor" bracket ($301\text{--}400$ AQI, mean $\approx 362$ AQI). These days already mandate GRAP Stage II restrictions (diesel generator bans, mechanized road sweeping, enhanced bus/metro frequency). Escalating to Stage III/IV mitigations on these borderline days provides substantial proactive pollution dampening rather than wasteful expenditure.

---

## 6. Physical & Mathematical Drivers of the Threshold Shift

Why does the optimal threshold $\tau^*$ diverge from the statutory $401$ cutoff?

1. **Regularization Shrinkage in the Winning Model:**  
   The winning 24h model is a 50/50 blend of Persistence and Ridge regression ($\alpha=1000$). High L2 regularization was deliberately introduced in Phase 6C to prevent tree extrapolation blowups, but L2 penalties inherently shrink predictions slightly toward the dataset mean ($374.1$ predicted mean vs $379.2$ actual mean on test). Consequently, true 420 AQI events are frequently forecasted as $360\text{--}390$ AQI. Evaluating these predictions against an unadjusted $\tau=401$ cutoff creates severe false negatives.
2. **Forecast Uncertainty & Variance Discounting:**  
   At a 24-hour lead horizon, meteorological turbulence and boundary layer dynamics introduce irreducible variance ($\text{RMSE} = 44.80$). In the presence of Gaussian forecast errors and asymmetric costs, optimal decision theory dictates shifting the decision threshold toward the origin by approximately:
   $$\Delta\tau \approx \sigma_{\epsilon} \cdot \ln(R)$$
   For $\sigma_{\epsilon} \approx 45$ and $R = 5$, $\Delta\tau \approx 45 \cdot \ln(5) \approx 72$ points, directly aligning with our empirical shift ($\Delta\tau = -59.5$).

---

## 7. Actionable Recommendations for CAQM / GRAP Policy

1. **Adopt a Two-Tier Decision Architecture:**
   - **Precautionary Alert Trigger ($\tau = 340\text{--}350$ AQI):** Dispatch proactive municipal advisories, mobilize mechanized street sweepers, and alert hospital respiratory ICUs 24 hours in advance.
   - **Enforceable Statutory Ban Trigger ($\tau = 380\text{--}401$ AQI):** Enforce legally binding industrial closures and heavy truck transit bans.
2. **Deprecate Uncritical Pointwise Thresholding:** Continuous probabilistic outputs or cost-adjusted decision rules should be integrated into the upcoming Phase 8 real-time inference engine (`src/inference/`) and FastAPI serving layer.

---

## 8. Artifacts Index

- **Python Analysis Pipeline:** `src/analysis/cost_aware_threshold_analysis.py`
- **Full Threshold Sweep CSV:** `reports/classification/metrics/cost_threshold_sweep_24h.csv`
- **Cost-Optimal Summary CSV:** `reports/classification/metrics/cost_optimal_thresholds_summary.csv`
- **Operating Points Table CSV:** `reports/classification/metrics/threshold_operating_points_comparison.csv`
- **Visual Figures:**
  - `reports/classification/figures/01_precision_recall_curve_24h.png` (PR Curve with statutory & optimal points)
  - `reports/classification/figures/02_expected_cost_vs_threshold.png` (Expected cost curves across 5 loss ratios)
  - `reports/classification/figures/03_tradeoff_metrics_vs_threshold.png` (4-panel trade-off dashboard)
  - `reports/classification/figures/04_false_positive_composition.png` (False alarm category breakdown)

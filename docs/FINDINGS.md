# Research findings (Tier 1 and 2 frozen-model results)

Moved out of the README. All numbers are scored on the **official** AQI with the frozen models; see `docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md` for the live basis. Sources: `reports/`.


## What went wrong during modeling

Tree models cannot predict above the maximum they saw in training (~347 AQI), so they under-predicted the 450–500 AQI
winter spikes and scored MAE 98.24 and R² −0.06 at 24h. Raw calendar features (e.g. month) made it worse by sending winter
rows into low-pollution monsoon leaves. The fix is to drop raw calendar features and blend persistence 50/50 with an
L2-regularised Ridge model on 49 causal features: the linear part extrapolates, persistence keeps local inertia. 24h MAE
fell from 98.24 to 34.11.
Details: [`reports/modeling/PHASE_6_FINAL_AUDIT.md`](reports/modeling/PHASE_6_FINAL_AUDIT.md).

## Causal analysis: the Diwali ban

A naive before/after comparison shows pollution jumping after Diwali 2025 (+135.6 AQI; +97.3 µg/m³ PM2.5), which would make
the ban look like a failure. The design fails its own checks: pre-trends are violated (AQI already rising +20.4 points/day in
the 14 days before), and a placebo on a non-event date returns a "significant" +24.3 AQI shift. With date-clustered standard
errors and trend plus weather controls (interrupted time series), the level jump is indistinguishable from zero (−10.6 AQI,
p = 0.51; +17.0 µg/m³ PM2.5, p = 0.59). **The ban's effect is not identifiable here.**

Hourly tracers show firecrackers caused an acute burst on festival night (PM2.5 up 8.0x to 960.7 µg/m³, SO₂ up 5.3x to
73.5 µg/m³) that dispersed within 18–24 hours; the weeks-long crisis that followed was driven by seasonal meteorology.
Details: [`reports/causal/diwali_ban_causal_analysis.md`](reports/causal/diwali_ban_causal_analysis.md).

## Risk classification and alerting

Forecasts map to the 6 CPCB categories (Good … Severe) and CAQM GRAP Stages I–IV. The Severe cutoff minimises expected
asymmetric cost on validation (Sep–Oct 2025), then is applied once to the winter test set. Validation has 2.4% Severe hours,
the test window 41.1%, which makes thresholds hard to transfer.

| Operating Policy | Decision Cutoff (AQI) | Val Severe Recall | Val Severe Precision | Test Severe Recall | Test Severe Precision | Test Missed Severe Hours | Test False Alarm Hours |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Statutory Fixed CPCB** | 401.0 | 20.8% | 32.2% | 61.08% | 73.86% | 1,568 h | 871 h |
| **Validation-optimal (5:1 Loss Ratio)** | **274.5** | **100.0%** | 9.81% | **99.83%** | 42.93% | **7 h** | 5,347 h |
| **Pragmatic Compromise** | 380.0 | 49.1% | 33.3% | 78.90% | 64.40% | 850 h | 1,757 h |

The aggressive cutoff buys recall at the cost of precision. At the same 274.5 cutoff, naive persistence scores recall 99.63%,
precision 43.03% and 5,314 false-alarm hours, essentially the same as the model, so this rule is **not** evidence of skill
beyond persistence. An earlier version selected the threshold on the test set; that leakage has been removed.
Details: [`reports/classification/cost_aware_threshold_analysis.md`](reports/classification/cost_aware_threshold_analysis.md).

## Tier 2 experiments (beyond the frozen models)

Do more data, other targets, weather or uncertainty estimates help? Selection used validation only; test was scored once.
None of these replace the frozen production models. See [`docs/TIER_2/`](docs/TIER_2/README.md) and the
[audit](docs/TIER_2/TIER_2_AUDIT.md).

| Experiment | Result |
| :--- | :--- |
| 24h hybrid trained on 2024 + 2025 (AQI recomputed for 2024) | Test MAE 34.02 vs 34.11 for the frozen model (skill +0.113 vs +0.110): a negligible change |
| Rolling-origin backtest, winters 2024 and 2025 | MAE skill vs persistence +0.099 [+0.059, +0.138] and +0.111 [+0.077, +0.145] |
| Raw PM2.5 forecast (test MAE skill vs persistence) | 1h +0.201 [+0.181, +0.219]; 6h +0.374 [+0.322, +0.418]; 24h −0.093 [−0.220, +0.010] (no edge) |
| Weather features for the 24h AQI forecast | Best causal-weather config: test MAE 33.89 vs 34.02 without weather (0.4%, well inside the CI); oracle weather is an upper bound only; fires not run |
| 80% prediction intervals (24h AQI) | Conformal test coverage 0.761 (target 0.80), width 142 vs 119 for a persistence band that covers 0.780 |
| P(AQI ≥ 401) | Brier 0.194 vs 0.196 for persistence (difference CI [−0.028, +0.024]); under-forecasts severe in the lowest probability bins |

A larger-compute rerun (random hyper-parameter search on validation, `T2_PROFILE=max`) lowered validation error by 1–2% but
did not improve held-out winter skill, and made the weather-ablation and Brier results slightly worse, so the results above
remain the headline. **Summary:** more winters and weather barely move the 24h point forecast, raw PM2.5 is forecastable at
1h and 6h, and the probabilistic outputs are not yet better than simple persistence baselines.

---


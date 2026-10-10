# Tier 2 — Make the model genuinely better

Tier 2 in `docs/IMPROVEMENT_PLAN.md` turns an honest-but-weak pipeline into one
that can actually beat persistence where it matters. Unlike Tier 1 (one
consolidated log), each task below has its own document.

| Task | Title | Status | Doc |
| :--- | :--- | :--- | :--- |
| T2.1 | Recompute CPCB AQI for 2023–2024 and retrain on prior winters (D7) | ✅ Done, audited (gate passes overall; weaker in Feb–May) | [T2.1_recompute_aqi.md](T2.1_recompute_aqi.md) |
| T2.2 | Rolling-origin backtest across winters | ✅ Done, audited (embargo + CIs added) | [T2.2_rolling_origin_backtest.md](T2.2_rolling_origin_backtest.md) |
| T2.3 | Forecast raw PM2.5 as an additional target | ✅ Done and rerun in Colab (1h/6h beat persistence; 24h does not) | [T2.3_pm25_target.md](T2.3_pm25_target.md) |
| T2.4 | Exogenous drivers (weather, fires) + ablation | ✅ Weather done and rerun in Colab (small gain); fires not run (needs FIRMS key) | [T2.4_exogenous_drivers.md](T2.4_exogenous_drivers.md) |
| T2.5 | Probabilistic / quantile forecasts + calibration | ✅ Done and rerun in Colab (intervals no better than a persistence band; Brier ties persistence) | [T2.5_probabilistic_forecasts.md](T2.5_probabilistic_forecasts.md) |

Full review of what was wrong and what changed: [TIER_2_AUDIT.md](TIER_2_AUDIT.md).

Guiding rules (from the plan): never select on test; every quoted number comes
from a script output file; always show persistence and skill next to a model.

## Max-compute robustness check (2026-10-10)

`T2_PROFILE=max` was run in Colab (random hyper-parameter search on validation, 10,000 bootstrap resamples). Results
are in `reports/modeling/{24h,pm25,exogenous,probabilistic}/max/`; the standard results stay the headline.

| Experiment | Standard | Max | Verdict |
| :--- | :--- | :--- | :--- |
| PM2.5 test MAE skill 1h / 6h / 24h | +0.201 / +0.374 / −0.093 | +0.199 / +0.376 / −0.090 | same |
| PM2.5 validation MAE 1h / 6h / 24h | 13.24 / 25.54 / 31.62 | 13.06 / 25.24 / 31.27 | slightly better |
| Rolling-origin skill 2024 / 2025 | +0.099 / +0.111 | +0.099 / +0.111 | identical, CIs tighter |
| Ablation, best deployable test MAE | 33.890 | 34.505 | worse |
| Median-forecast skill (24h AQI) | +0.062 | +0.055 | worse |
| Brier, P(AQI ≥ 401) (persistence 0.1958) | 0.1938 | 0.2057 | worse |
| Conformal test coverage | 0.761 | 0.755 | same |

Conclusion: more compute and tuning improved validation fit a little but not held-out winter skill (validation has a 2.4%
severe rate, the test winter 41.1%). Do not select from `smoke` runs; they only check that the code runs.

## Heavy compute on Colab

`notebooks/tier_2_colab.ipynb` runs **all** Tier 2 tasks (T2.1–T2.5 and the headline
table) against the project folder in Google Drive and writes the results back into
`reports/`. It has per-section toggles, fails loudly when a script fails, and only
displays outputs written during the current run (stale files are skipped unless
`SHOW_STALE = True`). Training is done there, not on the laptop.

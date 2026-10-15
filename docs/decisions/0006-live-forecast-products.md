# 0006. Live forecast products: a rule at 1h, models at 6h and 24h, PM2.5 at 1h and 6h

**Status:** accepted 2026-10-15.

**Context.** The live AQI is a trailing 24h mean of an hourly AQI, so `AQI(t+h) = AQI(t) + sum (H(t+k) - H(t+k-24)) / 24` and every hour leaving the window is
known at `t`. A parameter-free rule that assumes the entering hours equal the current hourly value ("window-update persistence") therefore explains most of the
short-horizon change. Evidence: `reports/modeling/live_retrain/window_update_baseline.csv`, `docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`.

**Decision.**

| Product | Served as | Reason |
| :--- | :--- | :--- |
| AQI 1h | Rule-based (24h-window update), no model file | Beats plain persistence by +0.55 on test; the retrained 1h LightGBM loses to the rule (-0.47 against it). |
| AQI 6h | Live-consistent LightGBM | +0.30 against persistence and against the rule: the skill is not the window arithmetic. |
| AQI 24h | Live-consistent hybrid, labelled low-skill | +0.09 against persistence. |
| PM2.5 1h, 6h | Live-consistent HistGradientBoosting, headline live forecast | Skill above zero with CIs excluding zero. |

Not published, kept off in `config/live.toml` `[forecast]` (the config refuses to switch them on):
- the 1h LightGBM (`models/live/aqi-1h-lgb-live-v1.*` stays, hash-pinned, but cannot be selected);
- PM2.5 24h (test skill -0.10; the project rule is no 24h PM2.5 forecast; the database constraint refuses it);
- the 24h interval (the 80% conformal interval covers 77.0% on test);
- P(severe) (Brier difference against persistence includes zero; severe rate 40.8% on test, 3.2% on validation).

**Consequences.**
- Model health scores AQI 1h and 6h against window-update persistence as well as plain persistence. The forecast job writes plain persistence on every row; the scorer
  derives the window-update reference from stored readings (Stage 4).
- The 1h product has no model hash: its registry row hashes `src/live/rules.py`, and its behaviour is pinned by `tests/test_aqi_causality.py` and `tests/test_serving.py`.
- The 1h claim is "rule-based, better than persistence", not "model skill".
- The forecast job serves `src/live/serving.py`; the frozen research models stay behind `src/live/models.py` for parity and the retrain's reference rows (ADR 0001).
- numpy and pandas move to 2.1.3 / 2.2.3 (the versions the live models were pickled with); the PM2.5 models do not unpickle under numpy 1.

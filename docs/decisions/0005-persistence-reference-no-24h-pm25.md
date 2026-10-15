# 0005. Persistence is the reference; no 24h PM2.5 forecast

**Status:** accepted.

**Context.** Official AQI is a 24-hour rolling average, so copying the last value is very hard to beat at short horizons.

**Decision.** Every model result is shown next to persistence on the same rows, as skill = 1 - MAE_model / MAE_persistence with day-block bootstrap CIs.
Skill is claimed only when the interval excludes zero. Thresholds and hyper-parameters are chosen on validation; the test window is scored once.
No 24h PM2.5 forecast is published: it does not beat persistence on test (`reports/modeling/live_pm25/`).

**Consequences.** Some horizons are labelled low-skill rather than dropped; the UI shows the persistence baseline beside each forecast.

# Case study: three things the live system taught the forecasts

The research phase produced models that beat persistence on a held-out winter. Putting them on a live feed exposed three
problems that the backtest could not. All numbers are from `reports/modeling/live_retrain/`, `reports/live/` and
`reports/metrics/`; skill = 1 - MAE_model / MAE_reference with 95% day-block bootstrap intervals, test window
2025-11-01 to 2025-12-31, scored once.

## 1. Train/serve skew

The live pipeline can only compute AQI from pollutants. That series averages about 5.5 points above the official CPCB AQI
the first models were trained on, so skill measured on the official basis does not carry over. Re-scoring the frozen
models on the live basis:

| Horizon | Frozen model vs persistence | Live-consistent retrain vs persistence |
| :--- | :---: | :---: |
| 1h | -0.084 [-0.421, +0.127] | +0.339 [+0.267, +0.395] |
| 6h | -0.046 [-0.235, +0.092] | +0.303 [+0.243, +0.351] |
| 24h | +0.080 [+0.041, +0.114] | +0.090 [+0.051, +0.126] |

The fix was to refit the same architectures with recomputed AQI as both input and target, scored on the input view the live
sources can actually supply (no NOx, NO or solar; no ITO weather). Calibrating the frozen models' inputs with an isotonic
map was tried first and lost to the retrain on validation at every horizon, so it was not adopted. A test checks that the
recomputed path never uses a value from after the issue hour.

## 2. A rule beats the model at 1h; the model wins at 6h

Recomputed AQI is a trailing 24h mean, so `AQI(t+h) = AQI(t) + sum (H(t+k) - H(t+k-24)) / 24`, and every hour leaving the
window is known at `t`. Window-update persistence uses that, has no fitted parameters, and is the right baseline.

| Horizon | Rule vs persistence | Model vs persistence | Model vs rule |
| :--- | :---: | :---: | :---: |
| 1h | +0.553 [+0.510, +0.591] | +0.344 [+0.273, +0.400] | -0.467 [-0.594, -0.375] |
| 6h | +0.007 [-0.114, +0.113] | +0.309 [+0.252, +0.355] | +0.304 [+0.243, +0.357] |

At 1h the rule recovers more than the model's whole gain (the model puts 91% of its gain on the current AQI and cannot
reconstruct the window); the "+0.34 at 1h" is real against persistence but is not forecasting skill. At 6h six unknown hours
enter the window, so the arithmetic stops helping and the model wins. The service therefore serves the rule at 1h and the
model at 6h (ADR 0006). The same discipline withholds 24h PM2.5 (test skill -0.102, interval includes zero) and labels 24h
AQI experimental.

A replay of the production code on stored readings (2026-09-01 to 2026-10-07) agrees: AQI 1h +0.514 [+0.460, +0.564], 6h
+0.206 [+0.124, +0.285], 24h -0.014 [-0.104, +0.058].

## 3. Dead live sources: probe, shadow mode, gate

The primary source, OpenAQ, runs days behind real time, and the alternative (data.gov.in) refuses connections. The response was to replace guesses with checks:

- **Probe from where the job runs.** `probe-sources.yml`, run on 2026-10-11 from a GitHub runner (US egress):
  `api.data.gov.in` refused the connection (a `curl` from an Indian network timed out too), and OpenAQ's newest value was
  91.8 h old, so the lag is the source's, not the network's (ADR 0002). An overlap check against the raw CSVs then fixed OpenAQ's
  units, hour convention and sensor choice (`docs/TIER_3/openaq_overlap_check.md`).
- **Shadow the fallback.** WAQI is ingested hourly into a separate table that forecast, scoring and API code cannot read
  (grants and tests enforce it), so it can be compared without being trusted.
- **Fix the gate before the data arrives.** PM only (its gas readings look implausible), ITO excluded, the hour offset chosen
  on the first half of the overlap and scored on the second, a per-station pass, run weekly with the result posted to a
  GitHub issue (ADR 0009). It currently fails because there is no overlap yet; dropping the gases would cost about 0.05 of
  6h skill on validation.
- **Say so in the product.** With no fresh data the forecast job records `stale` (not an alert), and the dashboard shows the
  data age and the last issued forecast labelled as past.

## What this does not show

No live forecast is being issued yet, so the live scoreboard is empty and the skill above is test-window and replay skill.
AQI 24h has low skill, and the Diwali-ban effect is not identifiable from this data. Architecture and decisions:
[`ARCHITECTURE.md`](ARCHITECTURE.md), [`decisions/`](decisions/README.md).

# 0001. Frozen research models vs live-consistent retrain

**Status:** accepted 2026-10-15.

**Context.** The research models (`models/lgb_model_*`, `models/24h/final/`) were trained on the official CPCB AQI. The live pipeline can only
compute AQI from QC'd pollutants (`compute_aqi`), and that series sits on average 5.5 points above the official one
(`reports/modeling/live_audit/`). On the recomputed basis the frozen models' skill over persistence is not distinguishable from zero.

**Decision.** Keep the frozen models untouched and hash-pinned as the research reference. Serve live forecasts from models refit on
recomputed AQI as both input and target, same architectures and features, stored in `models/live/` with their own hashes
(`config/live_model_hashes.json`). Calibrating recomputed AQI to the official scale was tried as a side check and loses to the retrain on validation.

**Consequences.** Two model families coexist; results for each are reported next to persistence on the same rows
(`docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`). Official-basis skill numbers must not be quoted for the live service.

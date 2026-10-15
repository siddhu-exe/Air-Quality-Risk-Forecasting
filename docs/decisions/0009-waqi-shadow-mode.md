# 0009. WAQI in shadow mode; OpenAQ stays primary

**Status:** accepted 2026-10-15.

**Context.** OpenAQ, the primary source, runs behind real time (40 hours on 2026-10-15, down from 88). WAQI is fresh but publishes US-EPA sub-indices, not concentrations, has no history, and its gas readings looked implausible against last October (`docs/TIER_3/waqi_stations.md`). Whether WAQI can serve as a fallback has to be decided from evidence on the same hours, not from one-off checks.

**Decision.**
- The hourly OpenAQ ingest is on (`ingest.yml`, minute 10). It is idempotent. A lagging source is recorded (`job_runs.details.age_hours`, shown daily in model health) but does not turn the workflow red when rows were written; the forecast job refuses stale data by itself.
- The forecast cron stays off until a source has been under 3 hours old for 24 hours straight.
- WAQI is ingested hourly (`shadow-waqi.yml`, minute 20), back-converted with `src/live/epa_aqi.py`, into **`aq.shadow_readings`**, a separate table (migration 009), not `live_readings`. That table has one row per station-hour, so a second source would overwrite or be overwritten by the primary one, and the forecast job reads it without a source filter. The shadow table is readable and writable by `job_writer` only: `api_readonly` has no grant, and tests assert that no forecast, scoring or API module mentions it.
- Each shadow run logs a per-pollutant comparison with OpenAQ on overlapping hours at offsets -1, 0 and +1 hour (WAQI's hour convention is unknown) in `job_runs.details`; `python -m src.live.shadow_compare --days 7` prints the evidence.

**Consequences.** After about a week of overlap we decide per pollutant whether WAQI can be a fallback, probably PM2.5 and PM10 only. Using it for forecasts would need its own ADR, a migration, a source adapter and a re-check of the models' skill on that input.

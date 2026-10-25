# 0009. WAQI in shadow mode; OpenAQ stays primary

**Status:** accepted 2026-10-15; fallback gate added 2026-10-17; stall escalation and Google reopened 2026-10-25 (below).

**Context.** OpenAQ, the primary source, runs behind real time (40 hours on 2026-10-15, down from 88). WAQI is fresh but publishes US-EPA sub-indices, not concentrations, has no history, and its gas readings looked implausible against last October (`docs/TIER_3/waqi_stations.md`). Whether WAQI can serve as a fallback has to be decided from evidence on the same hours, not from one-off checks.

**Decision.**
- The hourly OpenAQ ingest is on (`ingest.yml`, minute 10). It is idempotent. A lagging source is recorded (`job_runs.details.age_hours`, shown daily in model health) but does not turn the workflow red when rows were written; the forecast job refuses stale data by itself.
- The forecast cron stays off until a source has been under 3 hours old for 24 hours straight. *(Superseded 2026-10-17: the forecast and score crons are on. The forecast job records `stale` and stays green while nothing is fresh, so it starts producing forecasts by itself.)*
- WAQI is ingested hourly (`shadow-waqi.yml`, minute 20), back-converted with `src/live/epa_aqi.py`, into **`aq.shadow_readings`**, a separate table (migration 009), not `live_readings`. That table has one row per station-hour, so a second source would overwrite or be overwritten by the primary one, and the forecast job reads it without a source filter. The shadow table is readable and writable by `job_writer` only: `api_readonly` has no grant, and tests assert that no forecast, scoring or API module mentions it.
- Each shadow run logs a per-pollutant comparison with OpenAQ on overlapping hours at offsets -1, 0 and +1 hour (WAQI's hour convention is unknown) in `job_runs.details`; `python -m src.live.shadow_compare --days 7` prints the evidence.

**Consequences.** After about a week of overlap we decide per pollutant whether WAQI can be a fallback, probably PM2.5 and PM10 only. Using it for forecasts would need its own ADR, a migration, a source adapter and a re-check of the models' skill on that input.

## Update 2026-10-17: the fallback gate

**Context.** On 2026-10-17 the shadow table held 70 rows (7 stations, 12 hours, 2026-10-15 18:00 to 10-17 12:00 IST) and OpenAQ ended at 2026-10-13 22:00, so there were no overlapping hours and no comparison to make. The rule for when WAQI may be used had to be fixed before the data arrives, so it cannot be tuned on the data that judges it.

**Decision.** `src.live.shadow_compare.gate()` gives one PASS/FAIL, from these rules:
- **Scope.** PM2.5 and PM10 only. The gases are never used (WAQI's NO2/SO2/CO/O3 sat at the 2nd-4th percentile of last October, `docs/TIER_3/waqi_stations.md`), and the AQI would be recomputed from PM only.
- **ITO is excluded entirely.** WAQI has no ITO monitor; the mapped one (Major Dhyan Chand National Stadium) is a different instrument 1.9 km away. It is not scored, not counted towards the station minimum, and gets no WAQI-based forecast even if its numbers happen to agree.
- **Offset chosen once, on the first half.** The overlap hours are split in time at their median. The hour offset (-1, 0, +1; ties go to 0) is chosen per pollutant by the smallest MAE share on the first half, and the gate is scored on the second half at that offset.
- **Thresholds (second half).** The overlap spans at least 7 days; the stations that pass individually, pooled, have at least 150 paired hours per pollutant with corr >= 0.9, |bias| < 10% of the OpenAQ mean and MAE < 20% of the mean; and at least 5 stations pass individually.
- **Per station.** The same corr, bias and MAE tests are applied to each station on its own (at least 24 paired hours on the second half). A station that fails either pollutant gets no WAQI-based forecast, even if the network passes. A failing station does not count against the pooled figures (it is out anyway); its numbers are still reported.
- **Run weekly.** `waqi-gate.yml` (Mondays 04:30 UTC, or by hand) runs `python -m src.live.shadow_compare --gate --issue` and posts the result to the GitHub issue titled "WAQI fallback gate, weekly result [waqi-gate]" (opened the first time, commented on after). A FAIL is a result, not a broken job, so the workflow stays green. The gate reads stored rows only.

Two readings of the owner's wording, accepted by the owner on 2026-10-17: "at least 5 per station" means at least 5 of the 6 eligible stations pass, and each station needs at least 24 paired hours on the scoring half.

**PM-only audit (what dropping the gases costs).** `python -m src.evaluation.waqi_roundtrip_audit --pm-only` on the validation window (2025-09-01 to 10-31; frozen models, nothing re-fitted; AQI recomputed from PM2.5/PM10 only, with the PM sub-index required but the CPCB 3-pollutant rule relaxed to 1; PM also taken through concentration -> integer EPA AQI -> concentration). Report: `reports/modeling/live_audit/pm_only_audit.md`. Skill vs persistence, each scenario on its own recomputed AQI:

| Horizon | Full pollutants, recomputed AQI | PM-only, exact | PM-only, round trip |
| :--- | :---: | :---: | :---: |
| 1h | +0.044 [-0.053, +0.135] | +0.041 [-0.088, +0.154] | +0.043 [-0.087, +0.155] |
| 6h | +0.066 [-0.055, +0.171] | +0.016 [-0.098, +0.118] | +0.018 [-0.099, +0.119] |
| 24h | +0.038 [-0.011, +0.079] | +0.036 [-0.011, +0.078] | +0.039 [-0.008, +0.080] |

Reading: dropping the gases costs about 0.05 of skill at 6h and nothing visible at 1h and 24h, and every interval includes zero, including the full-pollutant control, so none of these is a measured skill. The PM-only AQI sits closer to the official AQI than the full recomputed one in this window (bias +2.2 vs +5.5 AQI points), because PM dominates in September-October; in a season where O3 or NO2 sets the AQI it will read low. The PM round trip through the EPA index costs no more than 1.8% of the PM mean. These are validation-window numbers on frozen models; the models actually served (`models/live/`) use the gases and would have to be re-fitted on PM-only inputs before WAQI could feed them.

**Consequences.** Nothing is switched. Until a source is fresh (OpenAQ) or WAQI passes this gate, the site stays in honest stale mode and shows the last issued forecast as history. If the gate passes, using WAQI still needs: a new ADR, a source adapter (`src/live/sources/`) writing to `live_readings` with its own source tag and PM-only masking, a PM-only re-fit of the live models on Colab, and parity and audit re-runs; the per-station list in the gate report is the list of stations allowed to use it.

**Source decision (2026-10-17).** OpenAQ stays the primary source. WAQI is the only fallback candidate, because it serves station measurements. Google Air Quality and OpenWeather are rejected: they return model estimates on a grid, not what a monitor measured, and the forecasts are trained on and scored against station data. IQAir is rejected because its station data is behind a paywall. A fallback source has to be station data and has to pass the gate above.

## Update 2026-10-25: a long stall is an incident; Google reopened

**Context.** OpenAQ's feed stopped at 2026-10-23 21:00 IST and the site had no fresh data for days with nobody told: stale is exit 0 by design, so nothing escalates however long it lasts (`docs/postmortems/2026-10-ingest-stall.md`). The same incident showed that a fixed 72 h fetch window loses hours the source delivers days late.

**Decision.**
- A lagging source is still not a code failure: the ingest stays green with status `stale`.
- A stall that lasts is an incident. After the ingest, `src/live/stall_watch.py` opens the GitHub issue "Live source stalled [live-stalled]" when no station has had a new reading for more than 48 hours, updates its body on later runs (no comment per run), and closes it when a station is fresh again by the ingest's own definition (newest reading within `stale_after_hours`). The threshold opens at 48 h and closes only on fresh data, so a source hovering around the threshold does not flap the issue.
- The ingest fetches 192 hours per run (was 72). `python -m src.live.ingest --from ... --to ...` re-ingests an explicit window to repair a hole.
- Scheduled GitHub cron runs are best effort (4 to 8 of 24 per day observed). Accepted for now; revisit if the primary source changes.
- **Google Air Quality is reopened.** The 2026-10-17 source decision above rejected it because it returns modelled values on a grid, not what a monitor measured. That reason stands as a risk, not a verdict: Google enters shadow mode (Phase 1 of `docs/ROADMAP.md`) and is judged by the same pre-registered gate as WAQI, on the same OpenAQ station data. Its rules are fixed in a new ADR before its data is compared.

**Consequences.** Opening the issue needs `issues: write` on the ingest workflow. A source that is permanently more than 48 h behind keeps one open issue, which is accurate.

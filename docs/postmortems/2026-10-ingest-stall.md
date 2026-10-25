# Postmortem: live data stopped at 2026-10-23 20:00 IST, and days were missing behind it

**Status:** resolved 2026-10-25 (window fix, repair, escalation). Open: none for this incident.
**Severity:** data-quality incident, no outage. The site stayed up and showed its stale state as designed.

## Summary

The newest hour in `aq.live_aqi` was 2026-10-23 20:00 IST. The ingest job did not stop: it ran 4 to 8 times a day throughout and recorded status `stale` every time. Two separate problems sat behind that:

1. **Upstream (not ours).** OpenAQ, the primary source, stopped receiving new CPCB values. Its own newest value for six stations is 2026-10-23 21:00 IST (our hour label 20:00); for ITO it is 2026-10-22 13:30. There is nothing newer to fetch.
2. **Ours.** The ingest re-fetched a fixed 72-hour window ending at "now". Whole days were missing from `aq.live_readings` (2026-10-14, 10-19, 10-20) although OpenAQ holds them (95 of 96 quarter-hour slots on each, checked on R K Puram PM2.5). The window is the likely reason: the missing days line up with hours that OpenAQ delivered after a 72 h window had already moved past them. OpenAQ publishes no ingestion timestamp, so the delivery time is inferred from the run windows and row arrivals, not observed.

## Impact

- No fresh readings since 2026-10-23 20:00 IST at the time of writing (about 2 days behind real time; the ingest is level with OpenAQ's own newest value). ITO is a further day behind.
- No forecast issued since 2026-10-15 16:12 IST. The forecast job recorded `stale` 44 times from 2026-10-17 and issued nothing. The site shows the last issued forecast labelled as past (commit 48f92b1).
- Missing days in the stored series (above, plus 2026-10-15 with 7 rows) until repaired on 2026-10-25.
- No wrong numbers were shown; nothing was fabricated or interpolated.

## Timeline (IST; from `aq.job_runs` and `aq.live_readings`)

| When | Event |
| :--- | :--- |
| 2026-10-11 | Source probe: OpenAQ newest value 91.8 h old (`docs/TIER_3/README.md`). |
| 2026-10-15 16:12 | Last successful forecast run. |
| 2026-10-15 23:12 | History backfill; it ends at the newest hour OpenAQ then had (10-13 22:00). |
| 2026-10-16 02:50 to 22:05 | 5 ingest runs fail with `ProgrammingError`: station ids reached psycopg2 as `numpy.int64`. Fixed in `ca76314` (2026-10-17 13:41), which casts them to `int`; a test pins it. |
| 2026-10-17 01:26 to 12:24 | 4 ingest runs fail with `SourceUnavailable` (no rows). `ca76314` and `a934136` then make a lagging source status `stale` (exit 0). |
| 2026-10-17 14:05 onward | Every ingest run is `stale`. OpenAQ is never within the 3 h limit in the whole period; the best freshest-station lag in any run was 7.6 h (2026-10-24). |
| 2026-10-18 to 10-23 | Days arrive in bursts with a lag of 8 h to 60 h. |
| 2026-10-23 20:00 | Newest hour stored. OpenAQ has nothing newer from here. |
| 2026-10-25 | Investigation; window fix; missing days repaired; escalation added. |

## Cause

- **Freshness loss:** upstream. OpenAQ's own `datetimeLast` for the stations is 2026-10-23 21:00 IST (ITO 10-22 13:30). The product is as current as OpenAQ is. OpenAQ was behind during the whole period (11 days of job history, never under 3 h), so this is a standing property of this source, not a one-off.
- **Missing days:** `lookback_hours` was capped at 72 and the window is anchored on the job's clock (`end = now - 1 h`), not on the data. An hour that arrives more than 72 h after it happened is never inside any later window.
- **Why nobody was told:** by design (ADR 0009, `a934136`) a lagging source is `stale`, exit 0, and not an alert. That keeps the workflow quiet, but nothing escalated however long it lasted.
- **Contributing:** the hourly cron ran 4 to 8 times a day, not 24. GitHub Actions delays and drops scheduled runs. This lost no data (each run re-fetches a window) but adds up to several hours of avoidable latency once the source is fresh.

## Fix

| Change | Where | State |
| :--- | :--- | :--- |
| Fetch 192 h per run (was 72); still one OpenAQ request per sensor. | `config/live.toml`, `MAX_LOOKBACK_HOURS` in `src/live/config.py`, test | done |
| `--from/--to` re-ingests an explicit window (idempotent, recorded in `job_runs.details.repair`). | `src/live/ingest.py`, tests | done |
| Repair, run 2026-10-25: 10-14 went from 0 to 159 readings, 10-15 from 7 to 156, 10-19 to 10-23 filled (150, 161, 158, 143, 120 readings). 10-18 stays at 98: OpenAQ itself only has part of that day. Counts from `aq.live_readings`. | production write via `--from/--to` | done |
| Escalation: issue "Live source stalled" after 48 h without a new reading, closed when a station is fresh. ADR 0009 updated: stale is still not a code failure, a long stall is an incident. | `src/live/stall_watch.py`, `ingest.yml`, tests | done |

## Prevention

- The window now reaches back 8 days, so a source that delivers days late no longer loses hours; the repair option covers anything older.
- A stall of 48 h or more now opens an issue, so it cannot go unnoticed.
- Scheduled-cron gaps are accepted for now and documented in `ingest.yml` and ADR 0009; revisit if the primary source changes.
- A single upstream feed can still stop the product. A second station-data source is Phase 1 of `docs/ROADMAP.md`; a stored-series hole check belongs in the monthly ops report (Phase 6).

## Sources

Figures come from read-only queries on 2026-10-25: `aq.job_runs` (jobs `ingest`, `forecast`, `shadow`), `aq.live_readings` (rows per day, newest hour per station), OpenAQ `/locations/{id}` (`datetimeLast`) and `/sensors/{id}/measurements` (R K Puram PM2.5, slots per day, 2026-10-12 to 10-23). They were ad-hoc queries, not committed scripts; the monthly ops report (Phase 6) will replace them with one. The missing days were verified on one station and one pollutant upstream; the repair counts are for all stations.

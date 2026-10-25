# Roadmap

Exit criteria and the evidence column below are drafts; the owner confirms them when a phase starts.

The aim is for this project to show what a data scientist or ML engineer with 3 to 5 years of experience does, not only that a model was built. That means:

1. operating a production ML system over months, not just shipping it;
2. managing the model lifecycle: drift, retraining, safe promotion, rollback;
3. evaluating decisions and impact, not only errors;
4. generalizing beyond one city;
5. writing it all down: decision records, ops reports, postmortems.

**Every phase must add evidence for at least one of these. A task that does not is not done at all: we do not take it on.** The principles that apply to all work are in `CLAUDE.md`.

## How a phase runs

- Each phase ends with a written report (what was done, the numbers, what failed) and **stops for the owner's approval** before the next one starts.
- A phase is "done" only when its exit criteria are met, tests and CI are green, and the docs are updated.
- Status values: `planned`, `in progress`, `awaiting approval`, `done`, `dropped` (with the reason).

| Phase | Theme | Evidence it adds | Status |
| :--- | :--- | :--- | :--- |
| 0 | Stabilize | operations, postmortems | done |
| 1 | Google Air Quality API as a candidate source | decisions, operations | in progress |
| 2 | Data scale | generalization | planned |
| 3 | Mumbai | generalization | planned |
| 4 | Model lifecycle | lifecycle | planned |
| 5 | Decisions and benchmarks | decision evaluation | planned |
| 6 | Operate | operations, documentation | planned |
| 7 | Grounded LLM briefing (optional) | decisions, documentation | planned |

## Phase 0: stabilize

- Find why the live data stopped (newest AQI 2026-10-23 20:00 IST) and fix what is ours. Write `docs/postmortems/2026-10-ingest-stall.md` (impact, timeline, cause, fix, prevention).
- Delete the stray root files `json`, `os`, `requests`; find out what created them and add a guard if it was a script bug.

**Exit criteria:** postmortem written; ingest window fix tested; hole repair done and counted; stall escalation in place; cron gaps documented; stray files gone (they were ImageMagick screenshots from `import` lines typed into a shell, not a script bug).

## Phase 1: Google Air Quality API as a candidate source

This supersedes the 2026-10-17 rejection of Google in ADR 0009 ("model estimates on a grid, not what a monitor measured"). The question is now decided by the gate, not by assumption.

- **Cost first.** Check Google's pricing and free tier against our call volume (7 stations hourly, plus history). Set a quota cap or budget alert before any scheduled job exists. Report the expected monthly cost to the owner.
- **Right index.** Request the local Indian index (CPCB) and pollutant concentrations, not only the Universal AQI. Universal AQI is never shown as if it were CPCB AQI.
- **Shadow only.** Ingest into `aq.shadow_readings` with `source='google'`. Never into `live_readings`, the models or the API.
- **Same pre-registered gate as WAQI**, run immediately on Google's 30-day history against OpenAQ station data on the overlap (about 2026-09-25 to 10-23): split-half lag selection, per-station verdicts, corr >= 0.9, |bias| < 10% of the mean, MAE < 20% of the mean, at least 5 of the eligible stations passing. Reported per pollutant and per station.
- **If it passes:** propose how it would feed the models (likely a re-fit on Google-shaped inputs, same protocol as the live-consistent retrain) and wait for the owner's decision.
- **If it fails:** record it in ADR 0009 and keep Google as display-only "current conditions", clearly labelled.

**Exit criteria:** cost reported and cap in place; shadow ingest running; gate report with per-pollutant and per-station tables; ADR 0009 updated with the verdict.

## Phase 2: data scale

- Read-only coverage audit: hourly coverage per station-year from OpenAQ for the 7 Delhi stations (2018 onward) and the Mumbai-metro stations (CPCB, MPCB, BMC, IITM).
- Run the OpenAQ overlap check on Delhi (unit traps are documented in `src/live/openaq_overlap_check.py`).
- Backfill Delhi 2018-2023 and the selected Mumbai stations with the existing backfill code, each in its own tagged source, with a recompute-AQI validation per period like T2.1. Check the Supabase size budget first.

**Exit criteria:** coverage table committed; overlap check per source; backfill validated per period; storage use before and after reported.

## Phase 3: Mumbai

- **Step 1, external validation.** Run the frozen Delhi live-consistent models on Mumbai stations and report skill against persistence and window-update persistence, with CIs. Does it transfer?
- **Step 2, only if the owner approves:** a multi-city re-fit (Colab bundle, same protocol), with city-level and station-level results.
- **Dashboard:** a city switcher (Delhi / Mumbai) with the same honest states.

**Exit criteria:** step 1 report with the transfer verdict; step 2 only after approval; dashboard switcher tested.

## Phase 4: model lifecycle

- Drift monitoring on inputs (PSI or similar) and on live skill.
- A scheduled retraining pipeline: the challenger runs in shadow and is promoted only if it beats the champion on live data by a pre-registered margin. One-command rollback. Everything recorded in the model registry.

**Exit criteria:** drift report generated by a script; one full challenger cycle (shadow, decision, promote or reject) recorded; rollback exercised once and documented.

## Phase 5: decisions and benchmarks

- Turn forecasts into a GRAP alert policy and evaluate it as a decision: hits, false alarms, lead time, cost of misses.
- Benchmark against the official forecasts (SAFAR, IITM AQEWS) if their data is accessible; otherwise document why not.

**Exit criteria:** policy evaluation with CIs against the do-nothing and persistence policies; benchmark result or a written reason it cannot be done.

## Phase 6: operate

- `docs/ops/YYYY-MM.md`: a monthly report generated by a script: live skill against baselines, uptime, data freshness (including holes per station-day), incidents, cost.

**Exit criteria:** the script runs from a make target; the first report is committed; the report lists every incident with a postmortem link.

## Phase 7 (optional, later): grounded LLM daily briefing

- A daily briefing that only uses numbers returned by our API, with an evaluation harness proving it never states a number the API did not return.

**Exit criteria:** harness results over a fixed set of days with zero ungrounded numbers; failures shown, not hidden.

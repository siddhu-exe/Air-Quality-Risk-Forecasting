# 0008. API contract: every forecast has a status and its references

**Status:** accepted 2026-10-15.

**Context.** The earlier frontend contract (`frontend/src/api/schemas.ts`) was drawn before ADR 0006: it centres on a 24h forecast with an 80% interval and P(severe), neither of which is published, and it assumes a forecast exists for every station every hour. In the Sep-Oct 2026 replay only 65-74% of station-hours got a forecast.

**Decision.** `GET /api/v1/*` (read-only, `backend/app/`) returns, for every station and product:
- `status = ok` with `value`, plain `persistence` and, for AQI, `windowUpdate`, both frozen on the forecast row at issue time (ADR 0006); or
- `status = unavailable` with `reason` copied from what the forecast job recorded (`stale`, `current AQI missing`, `insufficient history`, `core features missing`, a dropped product, or "the forecast job has not run recently"); or
- `status = withheld` for PM2.5 24h, with the policy reason.

An `unavailable` forecast whose job has stopped (or never ran) may also carry `lastIssued`: the newest live forecast ever issued for that station and product (looked back 30 days), with its `issuedAt`, `validAt` and value. It is history: it never replaces the missing value, is absent on `ok` forecasts, and the UI shows it only in a panel labelled as past (added 2026-10-17).

There is no interval and no P(severe) field. Products carry `kind` (`rule` or `model`), a `label` ("Rule-based (24h-window update)", "Experimental: about as accurate as assuming no change" for AQI 24h) and `experimental`. The GRAP view is indicative (stage of the current network mean AQI and of each station's current and 6h-forecast AQI) and says it is not an official advisory. Model health returns skill against persistence and, for AQI, against window-update persistence, plus data freshness, forecast coverage and job status. `/backtest` serves the report files copied into the image.

Every live response carries `dataAsOf`, `generatedAt` and `stale`. A database failure is a 503 that names no host or credential; `/health` degrades instead of failing. CORS allows only `FRONTEND_ORIGIN`. The API holds the read-only credential only and never loads a model.

**Consequences.** The frontend's zod schemas and mock data are rewritten to this contract in Stage 6 (the design's interval and P(severe) widgets go, "no forecast this hour" states are added). `docs/TIER_3/PLAN.md` section 5 is superseded by the models in `backend/app/models.py`.

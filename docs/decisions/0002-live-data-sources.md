# 0002. Live data sources

**Status:** accepted; the probe result is below; which source is fresh enough is still open (`docs/TIER_3/README.md`).

**Context.** The forecast needs hourly pollutant readings for seven Delhi stations plus a 336 h history for the feature window.

**Decision.**
- OpenAQ is the primary source, behind one source interface (`config/live.toml`).
- data.gov.in is a fallback, enabled only after it is verified from a runner.
- WAQI is a candidate third source (tag `waqi_backconverted`). It returns US-EPA sub-indices, not concentrations, has no history, and its gas values looked implausible,
  so it is added only if its skill criterion and gas checks pass (`docs/TIER_3/waqi_stations.md`).
- The CPCB CCR portal is not scraped.
- The ingest and forecast workflows stay manual (`workflow_dispatch`) until a source is fresh; the cron is added in the commit that switches the source.

**Consequences.** Every stored reading carries its source tag so sources can be compared and mixed rows are visible.

## Update 2026-10-11: the probe result

`probe-sources.yml` was run by hand on 2026-10-11 at 10:20 UTC from a GitHub-hosted runner (US egress), as the decision required.

- **data.gov.in:** `api.data.gov.in` refused the connection from the runner. A `curl` from an Indian network also timed out (and, from a sandbox, was refused), so the block is not specific to GitHub's runners. data.gov.in stays unverified and unused; its source adapter is refused unless `allow_unverified` is set.
- **OpenAQ:** reachable from the runner, and the newest value it returned was 91.8 h old, so the lag seen from the development machine is the source's, not a network effect.

**Consequence.** No live source was both reachable and fresh, which is what made the shadow feed and the fallback gate necessary (ADR 0009). The probe stays as a manual workflow for re-checking.

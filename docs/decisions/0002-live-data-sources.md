# 0002. Live data sources

**Status:** accepted; which source is fresh enough is still open (`docs/TIER_3/README.md`).

**Context.** The forecast needs hourly pollutant readings for seven Delhi stations plus a 336 h history for the feature window.

**Decision.**
- OpenAQ is the primary source, behind one source interface (`config/live.toml`).
- data.gov.in is a fallback, enabled only after it is verified from a runner.
- WAQI is a candidate third source (tag `waqi_backconverted`). It returns US-EPA sub-indices, not concentrations, has no history, and its gas values looked implausible,
  so it is added only if its skill criterion and gas checks pass (`docs/TIER_3/waqi_stations.md`).
- The CPCB CCR portal is not scraped.
- The ingest and forecast workflows stay manual (`workflow_dispatch`) until a source is fresh; the cron is added in the commit that switches the source.

**Consequences.** Every stored reading carries its source tag so sources can be compared and mixed rows are visible.

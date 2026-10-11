# Option: hourly ingest as an Azure Container Apps Job in Central India

**Status: write-up only. Nothing is built or created. Needs your decision, and only if the situation below occurs.**

## When this option applies

Use it only if **both** are true after the probe runs (`.github/workflows/probe-sources.yml`, `workflow_dispatch`):

1. `api.data.gov.in` refuses or times out from a GitHub-hosted runner, and
2. OpenAQ is still stale (its newest CPCB value was 88 hours old on 2026-10-11), so it cannot be the primary live source.

If a runner can reach data.gov.in, none of this is needed. If OpenAQ has caught up, OpenAQ becomes the primary source
(your earlier rule) and no proxy or Azure ingest is needed either.

## What it would be

The hourly **ingest** (and nothing else) runs as a scheduled Azure Container Apps **Job** in the Central India region,
so the request to data.gov.in leaves from an Indian cloud address. It writes to Supabase exactly as the GitHub job would.
Forecast, scoring and monitoring stay on GitHub Actions.

```
Azure Container Apps Job (Central India, cron "10 * * * *" UTC)  ->  data.gov.in  (+ Open-Meteo)
        |  DATABASE_URL (job_writer, Supabase pooler)
        v
Supabase  <--  GitHub Actions: forecast (hourly, :25), score (nightly), alerts
```

It reuses the same Python package and image tag pipeline as the API (build in GitHub Actions, push to GHCR, deploy
with OIDC). The ingest entry point would be `python -m src.live.ingest` (Stage 2), identical to what the workflow runs.

## What changes in the design

- The forecast workflow can no longer `needs:` the ingest job. It would run on its own cron a few minutes later and
  **check data freshness first**; if the newest reading is older than the stale limit it records a skipped run and
  stops. This is better practice than chaining anyway.
- Two schedulers instead of one (GitHub cron plus Azure cron). Missed or late runs can happen in either; the ingest
  is idempotent (`UNIQUE(station_id, ts)` upserts), so a catch-up run at :40 is harmless.
- One more thing to deploy and monitor, with its own failure mode. `job_runs` already records every run, so the
  monitoring rules (job failed 3 times in a row opens an issue) keep working unchanged.

## Exact Azure resources (you would create them; I would not)

| Resource | Notes |
| :--- | :--- |
| Resource group | e.g. `rg-delhi-air` (may already exist for the API) |
| Container Apps environment | region **Central India**; Consumption plan; the API's environment can be shared if it is in the same region (the API could stay elsewhere, but then it needs its own environment) |
| Log Analytics workspace | created with the environment |
| Container Apps **Job** | trigger type *Schedule*, cron `10 * * * *` (the schedule is evaluated in UTC), replica timeout about 5 minutes, 1 retry, 0.25 vCPU / 0.5 GiB |
| Federated credential on the existing app registration | so GitHub Actions can deploy the job image with OIDC (no password) |
| Job secrets | `DATABASE_URL`, `DATA_GOV_IN_API_KEY` as Container Apps secrets, never in the image |

**TODO(verify)** before relying on any of the following, because I could not confirm them from a primary source here:

- that Container Apps Jobs are available in Central India today;
- the current free grant and pricing for Consumption jobs (an hourly job of about a minute is very small, but check the
  number and that "our Azure credit" covers it);
- whether Consumption jobs get a stable outbound IP. By default they do not. If data.gov.in blocks by IP range rather than
  by country, an Azure datacenter range may be blocked too, and a fixed IP would need a workload-profile environment with a
  VNet and NAT gateway (more cost and setup). **The first thing to do is test, not build:** run one job execution and read
  whether data.gov.in answers.

## The risk that this does not help

The block, if there is one, may be on cloud/datacenter address ranges generally, not on non-Indian countries. An Azure
Central India address is Indian geographically but still a datacenter range. The probe from a GitHub runner tells us
about *that* range only. Cheapest test before committing to this option: run the same probe module once as a Container Apps
Job (or in a throwaway container in Central India) and look at the answer.

## Costs, in plain terms

- Money: expected to be a few cents a month, within a free grant, **TODO(verify)**.
- Effort: roughly one Dockerfile (shared with the API), one workflow step, the Azure resources above, and a freshness check
  in the forecast job.
- Ongoing: one more moving part, plus keeping the data.gov.in key as an Azure secret in addition to the GitHub secret.

## Alternatives I would not recommend

- A proxy or rented Indian IP: you ruled it out, and it adds an untrusted hop in front of an API key.
- Running the ingest from your own machine or a home server: not reliable hourly.
- Waiting for OpenAQ to catch up: acceptable as a stopgap with the backfill gap you already accepted, but it gives no live
  data until the upstream feed recovers.

## Decision needed (only if the situation applies)

Build the Azure ingest job as described, test the Central India route first with a one-off run, or stay on OpenAQ and accept
stale data until it recovers?

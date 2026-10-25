# Google Air Quality API: cost, caps and setup

Decision and gate rules: `docs/decisions/0010-google-air-quality-shadow-gate.md`. Code: `src/live/sources/google_aq.py`, `src/live/google_shadow.py`, `.github/workflows/shadow-google.yml`.

## What is billed

One SKU, **Air Quality Usage** (Essentials). A billable event is a successful request: one `currentConditions` call, one **page** of `history` (168 hours at most), one page of `forecast`. Source: Google Maps Platform SKU details page, checked 2026-10-25.

| Price list | Free per month | Then, per 1,000 requests |
| :--- | ---: | :--- |
| Global (SKU 90A9-B3FA-4A12) | 10,000 | $5.00 up to 100,000, then lower tiers |
| India (SKU 03A0-8EE9-1B37) | 70,000 | $0.50 up to 5,000,000 |

Which list applies follows the billing account. The billing report shows the SKU name: "Air Quality Usage" is global, "Air Quality Usage (India)" is the India list. Check it after the first few requests.

The $300 / 90-day Free Trial credit can be spent on Google Maps Platform services (Google's "Getting started with Google Maps Platform" page), so during the trial nothing here is charged to a card in either case. Unspent trial credit expires with the trial; the monthly free allowance above is what continues afterwards.

## Expected volume and cost (arithmetic, not a measurement)

| Item | Requests per month |
| :--- | ---: |
| Current conditions, 7 stations x 24 h x 31 days | 5,208 |
| One-off 30-day history, 7 stations x 5 pages | 35 |
| Later: Google's forecast endpoint as the Phase 5 benchmark (7 stations, one or two pages a day) | up to about 430 |
| **Total, expected** | **about 5,700** |

- Global list: under the 10,000 free requests, so **$0 per month**, with roughly 43% headroom.
- India list: under 70,000, so **$0 per month**.
- GitHub's hourly cron actually runs 4 to 8 times a day, so real use is lower.
- Adding a second city of seven stations (Phase 3) takes the hourly total to about 10,400: about $2 per month on the global list, still $0 on the India list.

Guards in the code, independent of the console: `--max-requests` (default 60 per run) and a daily cap of 300 requests per IST day, read from `job_runs`. At 300 a day the worst a bug can spend in a month is 9,300 requests, under the global free allowance.

## What you must set in the Google Cloud console (before the hourly workflow is scheduled)

The menu names may differ slightly; the settings are what matter.

1. **Quota cap.** APIs & Services > Enabled APIs > Air Quality API > Quotas & System Limits. Set the per-day request limit if the page offers one, to **400 per day** (the code guard is 300, so the console cap is the backstop; 400 a day is at most 12,400 a month, about $12 on the global list if everything went wrong, $0 on the India list). A per-minute quota alone cannot bound daily spend.
2. **Budget alert.** Billing > Budgets & alerts > Create budget, scoped to this project. Amount **$5**, alerts at 50%, 90% and 100%, email to you. A budget only notifies; it does not stop spending, which is why the quota cap comes first.
3. **Restrict the key.** APIs & Services > Credentials > the key > API restrictions: **Air Quality API only**. An application restriction (IP or referrer) does not fit GitHub-hosted runners.
4. **Repository secret.** Add `GOOGLE_AIR_QUALITY_API_KEY` under Settings > Secrets and variables > Actions.
5. Tell the assistant when 1 to 4 are done; only then is the `schedule:` in `shadow-google.yml` enabled.

## Running it

```bash
FORCE_IPV4=1 python -m src.live.google_shadow --dry-run               # 7 requests, writes nothing
FORCE_IPV4=1 python -m src.live.google_shadow --history-days 30       # one-off, 35 requests, tag google_history
FORCE_IPV4=1 python -m src.live.shadow_compare --gate --source google_history --days 40
```

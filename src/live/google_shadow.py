"""Google Air Quality in shadow mode: concentrations and the local CPCB index -> ``aq.shadow_readings`` (source ``google``).

    python -m src.live.google_shadow --dry-run                    # one request per station, print, write nothing
    python -m src.live.google_shadow                              # current hour for the 7 stations
    python -m src.live.google_shadow --history-days 30            # one-off: the last 30 days (5 pages per station), tag google_history

Nothing written here feeds forecasts, the AQI or the API (ADR 0010, same isolation as WAQI in ADR 0009). Cost control: a run
refuses to start if its planned requests exceed ``--max-requests`` or would take today's total past ``DAILY_REQUEST_CAP``; the
number of requests used is recorded in ``job_runs.details`` (job ``shadow``, ``details.source = 'google'``). This is a guard in
addition to, not instead of, the quota cap and budget alert in the Google Cloud console (``docs/TIER_3/GOOGLE_AIR_QUALITY.md``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import pandas as pd

from src.live.log import configure as configure_logging
from src.live.log import get_logger
from src.live.sources import google_aq
from src.live.waqi_shadow import ShadowStore

log = get_logger(__name__)

DAILY_REQUEST_CAP = 300  # a normal day is 168 (7 stations x 24 hours)
DEFAULT_MAX_REQUESTS = 60
STATIONS = "select station_id, station_name, latitude, longitude from aq.stations order by station_id"
REQUESTS_TODAY = """
select coalesce(sum((details ->> 'requests')::int), 0) from aq.job_runs
where job = 'shadow' and details ->> 'source' = 'google'
  and (started_at at time zone 'Asia/Kolkata')::date = (now() at time zone 'Asia/Kolkata')::date
"""


class GoogleShadowStore(ShadowStore):
    def stations(self) -> dict[str, tuple[int, float, float]]:
        self._cur.execute(STATIONS)
        return {name: (int(i), float(lat), float(lon)) for i, name, lat, lon in self._cur.fetchall()}

    def requests_today(self) -> int:
        self._cur.execute(REQUESTS_TODAY)
        return int(self._cur.fetchone()[0])


def plan_requests(n_stations: int, history_days: int | None) -> int:
    return n_stations * (google_aq.pages_needed(history_days * 24) if history_days else 1)


def fetch_rows(
    stations: dict[str, tuple[int, float, float]],
    key: str,
    budget: google_aq.RequestBudget,
    history_days: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Rows for every station and the per-station errors (a failing station never stops the others)."""
    rows, errors = [], {}
    for name, (_id, lat, lon) in stations.items():
        try:
            if history_days:
                infos = list(google_aq.history(lat, lon, key, budget, history_days * 24))
            else:
                infos = google_aq.current(lat, lon, key, budget)
            rows += [google_aq.hour_row(name, info) for info in infos]
        except google_aq.BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - recorded by type; a message could echo a URL
            errors[name] = type(exc).__name__
    return pd.DataFrame(rows), errors


def run(
    store: GoogleShadowStore,
    key: str,
    history_days: int | None = None,
    max_requests: int = DEFAULT_MAX_REQUESTS,
    dry_run: bool = False,
) -> dict:
    stations = store.stations()
    planned = plan_requests(len(stations), history_days)
    if planned > max_requests:
        raise google_aq.BudgetExceeded(f"{planned} requests planned, --max-requests is {max_requests}")
    today = store.requests_today()
    if today + planned > DAILY_REQUEST_CAP:
        raise google_aq.BudgetExceeded(
            f"{today} requests already today + {planned} planned > daily cap {DAILY_REQUEST_CAP}"
        )
    budget = google_aq.RequestBudget(max_requests)
    run_id = 0 if dry_run else store.start_run("shadow")
    tag = google_aq.HISTORY_TAG if history_days else google_aq.SOURCE_TAG
    details: dict[str, Any] = {
        "source": google_aq.SOURCE_TAG,
        "tag": tag,
        "planned_requests": planned,
        "history_days": history_days,
    }
    written, status, error = 0, "failed", None
    try:
        rows, errors = fetch_rows(stations, key, budget, history_days)
        details.update(fetch_errors=errors, requests=budget.used)
        if rows.empty:
            error = "no Google hour could be read"
        else:
            details["newest_hour_utc"] = str(rows["waqi_time"].max().tz_convert("UTC"))
            if not dry_run:
                written = store.upsert_shadow(rows, {n: v[0] for n, v in stations.items()}, tag)
            status = "success" if not errors else "partial"
    except Exception as exc:  # record a short, key-free message and re-raise
        details["requests"] = budget.used
        if not dry_run:
            store.finish_run(run_id, "failed", written, type(exc).__name__, details)
        raise
    if not dry_run:
        store.finish_run(run_id, status, written, error, details)
    return {"status": status, "rows": written, "error": error, "details": details, "frame": rows}


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and convert; write nothing")
    parser.add_argument(
        "--history-days", type=int, help="fetch this many days of history instead of the current hour (max 30)"
    )
    parser.add_argument(
        "--max-requests", type=int, default=DEFAULT_MAX_REQUESTS, help="refuse a run that plans more requests"
    )
    args = parser.parse_args(argv)
    if args.history_days is not None and not 1 <= args.history_days <= google_aq.MAX_HISTORY_HOURS // 24:
        parser.error("--history-days must be between 1 and 30")
    key = google_aq.api_key()
    with GoogleShadowStore() as store:
        result = run(store, key, args.history_days, args.max_requests, args.dry_run)
    if args.dry_run:
        print(result["frame"].drop(columns=["raw_iaqi"]).round(2).to_string(index=False))
    log.info(
        "status=%s rows=%s requests=%s errors=%s",
        result["status"],
        result["rows"],
        result["details"].get("requests"),
        result["details"].get("fetch_errors"),
    )
    return 0 if result["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())

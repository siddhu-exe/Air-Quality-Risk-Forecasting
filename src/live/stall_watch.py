"""Escalate a long source stall to a GitHub issue (ADR 0009): "Live source stalled", closed again when the source is fresh.

A lagging source is a data condition, so the ingest stays green (status ``stale``). A stall that lasts is an incident, so this
step, run after every ingest, looks at the newest stored reading of the live source:
  * older than ``STALL_AFTER_HOURS``: open the issue, or update its body (no comment per run, runs are hourly);
  * at least one station back within ``stale_after_hours`` (the ingest's own definition of fresh): close the issue with a comment;
  * in between: nothing. Opening at 48 h and closing only on fresh data means a source hovering around the threshold does not
    flap the issue.

    python -m src.live.stall_watch [--dry-run]       # needs DATABASE_URL; GITHUB_TOKEN and GITHUB_REPOSITORY unless --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from src.live.config import load_config
from src.live.db import connect
from src.live.score import find_open_issue, github_call

KST = "Asia/Kolkata"
KEY = "live-stalled"
TITLE = "Live source stalled"
LABEL = "live-source"
STALL_AFTER_HOURS = 48.0
BACKFILL_SOURCES = ("local_csv_2026",)  # history loaded by hand; not a live source

NEWEST_PER_STATION = """
select s.station_name, max(r.ts)
from aq.stations s left join aq.live_readings r
  on r.station_id = s.station_id and r.source <> all(%s)
group by s.station_name order by s.station_name
"""


def age_hours(newest: pd.Timestamp | None, now: pd.Timestamp) -> float | None:
    """Hours since the end of the newest reading's hour (a reading labelled T covers [T, T+1h)); None when there is none."""
    return (
        None
        if newest is None or pd.isna(newest)
        else round((now - (newest + pd.Timedelta(hours=1))).total_seconds() / 3600, 1)
    )


def decide(
    newest_age: float | None, issue_open: bool, *, stale_after: float, stall_after: float = STALL_AFTER_HOURS
) -> str:
    """One of ``open``, ``refresh``, ``close``, ``none``. ``newest_age`` is the age of the freshest station (None = no data)."""
    if newest_age is None or newest_age > stall_after:
        return "refresh" if issue_open else "open"
    if newest_age <= stale_after and issue_open:
        return "close"
    return "none"


def body(newest: dict[str, pd.Timestamp | None], now: pd.Timestamp, stall_after: float) -> str:
    rows = [
        f"| {name} | {ts.strftime('%Y-%m-%d %H:%M') if ts is not None and not pd.isna(ts) else 'no reading'} | "
        f"{age_hours(ts, now) if age_hours(ts, now) is not None else '-'} |"
        for name, ts in newest.items()
    ]
    return "\n".join(
        [
            f"No station has had a new reading for more than {stall_after:.0f} hours (checked {now.strftime('%Y-%m-%d %H:%M')} IST).",
            "",
            "| Station | Newest hour label (IST) | Age (h) |",
            "| :--- | :--- | ---: |",
            *rows,
            "",
            "The ingest keeps running and the site shows its stale state; this issue closes itself when a station is fresh again. "
            "Background and the history of this source: `docs/postmortems/2026-10-ingest-stall.md`, ADR 0009.",
        ]
    )


def newest_per_station() -> dict[str, pd.Timestamp | None]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(NEWEST_PER_STATION, (list(BACKFILL_SOURCES),))
        rows = cur.fetchall()
    return {name: None if ts is None else pd.Timestamp(ts).tz_convert(KST).tz_localize(None) for name, ts in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the decision and the issue body; touch no issue")
    args = parser.parse_args(argv)
    cfg = load_config()
    now = pd.Timestamp.now(tz=KST).tz_localize(None)
    newest = newest_per_station()
    ages = [a for a in (age_hours(ts, now) for ts in newest.values()) if a is not None]
    freshest = min(ages) if ages else None
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    issue = None if args.dry_run else find_open_issue(KEY, repo, token, LABEL)
    action = decide(freshest, issue is not None, stale_after=cfg.stale_after_hours)
    print(f"freshest station {freshest} h old; threshold {STALL_AFTER_HOURS:.0f} h; issue action: {action}")
    if args.dry_run:
        print(body(newest, now, STALL_AFTER_HOURS))
        return 0
    base = f"https://api.github.com/repos/{repo}"
    if action == "open":
        github_call(
            token,
            "POST",
            f"{base}/issues",
            {"title": f"{TITLE} [{KEY}]", "body": body(newest, now, STALL_AFTER_HOURS), "labels": [LABEL]},
        )
    elif action == "refresh":
        github_call(token, "PATCH", f"{base}/issues/{issue['number']}", {"body": body(newest, now, STALL_AFTER_HOURS)})
    elif action == "close":
        github_call(
            token,
            "POST",
            f"{base}/issues/{issue['number']}/comments",
            {"body": f"A station is fresh again (freshest {freshest} h old)."},
        )
        github_call(token, "PATCH", f"{base}/issues/{issue['number']}", {"state": "closed"})
    return 0


if __name__ == "__main__":
    sys.exit(main())

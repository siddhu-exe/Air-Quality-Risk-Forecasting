"""WAQI in shadow mode: hourly feeds -> back-converted concentrations -> ``aq.shadow_readings``.

    python -m src.live.waqi_shadow [--dry-run]

Nothing written here feeds forecasts, AQI or the API: the forecast job and the API read ``live_readings``/``live_aqi`` only, and
``api_readonly`` has no access to the shadow table (migration 009). Each run also compares the last 24 hours of shadow rows with
OpenAQ's on overlapping hours and keeps the result in ``job_runs.details`` (job ``shadow``); the evidence for deciding whether WAQI
can be a fallback is ``python -m src.live.shadow_compare``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from src.live import shadow_compare
from src.live.epa_aqi import from_aqi
from src.live.log import configure as configure_logging
from src.live.log import get_logger
from src.live.sources import waqi
from src.live.store import Store

KST = "Asia/Kolkata"
log = get_logger(__name__)

UPSERT_SHADOW = """
insert into aq.shadow_readings (station_id, ts, source, pm25, pm10, no2, so2, co, o3, raw_iaqi, waqi_time)
values %s
on conflict (station_id, ts, source) do update set pm25 = excluded.pm25, pm10 = excluded.pm10, no2 = excluded.no2,
  so2 = excluded.so2, co = excluded.co, o3 = excluded.o3, raw_iaqi = excluded.raw_iaqi, waqi_time = excluded.waqi_time,
  ingested_at = now()
"""
SELECT_SHADOW = """
select station_id, ts, pm25, pm10, no2, so2, co, o3 from aq.shadow_readings where source = %s and ts > %s order by ts
"""
SELECT_PRIMARY = """
select station_id, ts, pm25, pm10, no2, so2, co, o3 from aq.live_readings where source = 'openaq' and ts > %s order by ts
"""


def feed_row(station: str, data: dict) -> dict:
    """One shadow row from a WAQI feed: the feed time floored to the hour, ``iaqi`` converted back to concentrations."""
    stamp = pd.Timestamp(data["time"]["iso"]).tz_convert(KST)
    iaqi = {k: float(v["v"]) for k, v in data.get("iaqi", {}).items() if k in waqi.POLLUTANTS and "v" in v}
    row: dict[str, Any] = {
        "station_name": station,
        "ts": stamp.floor("h"),
        "waqi_time": stamp,
        "raw_iaqi": iaqi,
    }
    for pollutant in waqi.POLLUTANTS:
        row[pollutant] = float(from_aqi(pollutant, [iaqi[pollutant]])[0]) if pollutant in iaqi else np.nan
    return row


def fetch_rows(key: str, fetch: Any = waqi.fetch_feed) -> tuple[pd.DataFrame, dict]:
    """Rows for every mapped station and the per-station errors (a failing station never stops the others)."""
    rows, errors = [], {}
    for station, (uid, _match) in waqi.MAPPING.items():
        try:
            rows.append(feed_row(station, fetch(uid, key)))
        except Exception as exc:  # noqa: BLE001 - recorded by type; the message could carry a URL with the token
            errors[station] = type(exc).__name__
    return pd.DataFrame(rows), errors


class ShadowStore(Store):
    def upsert_shadow(self, rows: pd.DataFrame, station_ids: dict[str, int]) -> int:
        from psycopg2.extras import Json, execute_values

        def cell(value: float) -> float | None:
            return None if value is None or np.isnan(value) else float(value)

        values = [
            (
                station_ids[r.station_name],
                r.ts.to_pydatetime(),
                waqi.SOURCE_TAG,
                *(cell(getattr(r, p)) for p in waqi.POLLUTANTS),
                Json(r.raw_iaqi),
                r.waqi_time.to_pydatetime(),
            )
            for r in rows.itertuples()
        ]
        if values:
            execute_values(self._cur, UPSERT_SHADOW, values, page_size=100)
        return len(values)

    def _frame(self, sql: str, args: tuple) -> pd.DataFrame:
        self._cur.execute(sql, args)
        frame = pd.DataFrame(self._cur.fetchall(), columns=["station_id", "ts", *waqi.POLLUTANTS])
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.tz_convert(KST).dt.tz_localize(None)
        return frame

    def shadow_since(self, since: pd.Timestamp) -> pd.DataFrame:
        return self._frame(SELECT_SHADOW, (waqi.SOURCE_TAG, since.to_pydatetime()))

    def primary_since(self, since: pd.Timestamp) -> pd.DataFrame:
        return self._frame(SELECT_PRIMARY, (since.to_pydatetime(),))


def run(
    store: ShadowStore, station_ids: dict[str, int], key: str, fetch: Any = waqi.fetch_feed, dry_run: bool = False
) -> dict:
    run_id = 0 if dry_run else store.start_run("shadow")
    details: dict = {"source": waqi.SOURCE_TAG}
    written, status, error = 0, "failed", None
    try:
        rows, errors = fetch_rows(key, fetch)
        details["fetch_errors"] = errors
        if rows.empty:
            error = "no WAQI feed could be read"
        else:
            details["newest_feed_time"] = {r.station_name: str(r.waqi_time) for r in rows.itertuples()}
            if not dry_run:
                written = store.upsert_shadow(rows, station_ids)
                since = pd.Timestamp.now(tz=KST) - pd.Timedelta(hours=24)
                table = shadow_compare.compare(
                    store.shadow_since(since), store.primary_since(since - pd.Timedelta(hours=2))
                )
                details["overlap_24h"] = json.loads(table.round(4).to_json(orient="records"))
            status = "success" if not errors else "partial"
    except Exception as exc:  # record a short, key-free message and re-raise
        if not dry_run:
            store.finish_run(run_id, "failed", written, type(exc).__name__, details)
        raise
    if not dry_run:
        store.finish_run(run_id, status, written, error, details)
    return {"status": status, "rows": written, "error": error, "details": details}


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and convert; write nothing")
    args = parser.parse_args(argv)
    from src.features.compute_cpcb_aqi import STATION_IDS

    key = waqi.token()
    if args.dry_run:
        rows, errors = fetch_rows(key)
        print(
            rows.drop(columns=["raw_iaqi"]).round(2).to_string(index=False) if len(rows) else "no feeds", errors or ""
        )
        return 0
    with ShadowStore() as store:
        result = run(store, STATION_IDS, key)
    log.info(
        "status=%s rows=%s error=%s errors=%s",
        result["status"],
        result["rows"],
        result["error"],
        result["details"].get("fetch_errors"),
    )
    return 0 if result["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())

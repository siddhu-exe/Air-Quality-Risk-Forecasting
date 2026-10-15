"""All database access for the live ingest, in one place. Connects through ``src.live.db`` (DATABASE_URL).

Write rules (tests assert the SQL text):
  * readings are upserted on (station_id, ts) and a row is only refreshed by the SAME source tag, so a
    hand-loaded CSV row is never overwritten and two live sources do not fight over an hour (first writer wins);
  * no DELETE anywhere; the job role could not run one anyway.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from src.live.qc import VALUE_COLUMNS

READING_COLUMNS = ["station_id", "ts", *VALUE_COLUMNS, "weather_source", "qc_flags", "source"]
UPSERT_READINGS_SAME_SOURCE = f"""
insert into aq.live_readings ({", ".join(READING_COLUMNS)}) values %s
on conflict (station_id, ts) do update set
  {", ".join(f"{c} = excluded.{c}" for c in READING_COLUMNS[2:])}, ingested_at = now()
where aq.live_readings.source = excluded.source
"""
UPSERT_AQI = """
insert into aq.live_aqi (station_id, ts, aqi) values %s
on conflict (station_id, ts) do update set aqi = excluded.aqi, computed_at = now()
"""
SELECT_RECENT_POLLUTANTS = """
select station_id, ts, pm25, pm10, no2, so2, nh3, co, o3
from aq.live_readings where station_id = any(%s) and ts >= %s order by station_id, ts
"""


def _clean(value):
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else value


def reading_tuples(readings: pd.DataFrame):
    """Rows for ``UPSERT_READINGS_*``: (station_id, tz-aware ts, values..., weather_source, qc_flags json, source)."""
    from psycopg2.extras import Json

    ts = pd.DatetimeIndex(readings.index).tz_localize("Asia/Kolkata")
    for position, (_, row) in enumerate(readings.iterrows()):
        yield (
            int(row.station_id),
            ts[position].to_pydatetime(),
            *[_clean(float(row[c])) for c in VALUE_COLUMNS],
            row.weather_source,
            Json(row.qc_flags),
            row.source,
        )


def aqi_tuples(aqi: pd.DataFrame):
    ts = pd.DatetimeIndex(aqi.hour).tz_localize("Asia/Kolkata")
    for position, row in enumerate(aqi.itertuples()):
        yield int(row.station_id), ts[position].to_pydatetime(), float(row.aqi)


class Store:
    """Real store: one connection per ``Store`` use, committed by the caller via ``close``/context manager."""

    def __init__(self, var: str = "DATABASE_URL"):
        from src.live.db import connect

        self._cm = connect(var)
        self._conn = self._cm.__enter__()
        self._cur = self._conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cur.close()
        return self._cm.__exit__(exc_type, exc, tb)

    def start_run(self, job: str) -> int:
        self._cur.execute(
            "insert into aq.job_runs (job, github_run) values (%s, %s) returning id",
            (job, os.environ.get("GITHUB_RUN_ID")),
        )
        run_id = self._cur.fetchone()[0]
        self._conn.commit()  # visible even if the run later fails
        return run_id

    def finish_run(self, run_id: int, status: str, rows: int, error: str | None, details: dict) -> None:
        self._cur.execute(
            "update aq.job_runs set status=%s, finished_at=clock_timestamp(), rows_written=%s, error=%s, details=%s where id=%s",
            (status, rows, error, json.dumps(details, default=str), run_id),
        )
        self._conn.commit()

    def upsert_readings(self, readings: pd.DataFrame) -> int:
        from psycopg2.extras import execute_values

        rows = list(reading_tuples(readings))
        if rows:
            execute_values(self._cur, UPSERT_READINGS_SAME_SOURCE, rows, page_size=1000)
        return len(rows)

    def recent_pollutants(self, station_ids: list[int], since: pd.Timestamp) -> pd.DataFrame:
        self._cur.execute(
            SELECT_RECENT_POLLUTANTS,
            (list(station_ids), since.tz_localize("Asia/Kolkata") if since.tzinfo is None else since),
        )
        columns = ["station_id", "ts", "pm25", "pm10", "no2", "so2", "nh3", "co", "o3"]
        frame = pd.DataFrame(self._cur.fetchall(), columns=columns)
        frame["hour"] = pd.to_datetime(frame["ts"], utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
        return frame.drop(columns="ts")

    def upsert_aqi(self, aqi: pd.DataFrame) -> int:
        from psycopg2.extras import execute_values

        rows = list(aqi_tuples(aqi))
        if rows:
            execute_values(self._cur, UPSERT_AQI, rows, page_size=1000)
        return len(rows)


class NullStore:
    """Dry run: nothing is read or written; history for the AQI window is empty."""

    def start_run(self, job: str) -> int:
        return 0

    def finish_run(self, run_id, status, rows, error, details) -> None:
        pass

    def upsert_readings(self, readings: pd.DataFrame) -> int:
        return len(readings)

    def recent_pollutants(self, station_ids, since) -> pd.DataFrame:
        return pd.DataFrame(columns=["station_id", "pm25", "pm10", "no2", "so2", "nh3", "co", "o3", "hour"])

    def upsert_aqi(self, aqi: pd.DataFrame) -> int:
        return len(aqi)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

"""Backfill ``aq.live_readings`` and ``aq.live_aqi`` with 2026 history (decision D3).

Sources, tagged per row in ``live_readings.source``:
  * ``local_csv_2026``: the project's own raw CSVs, 2026-01-01 .. 2026-08-31 (six stations; Dwarka-Sector 8 has
    no 2026 file). Same numbers the models were trained on.
  * ``openaq``: OpenAQ 15-minute data converted to hourly (see ``src/live/openaq.py``), 2026-09-01 .. the newest
    complete hour OpenAQ has. OpenAQ's feed was ~88 hours stale on 2026-10-11, so history ends there until a
    live source catches up; forecasts skip stations without enough recent data and record why.

All values go through ``src/live/qc.py`` (cell-level; flags kept in ``qc_flags``). ``live_aqi`` is recomputed from
the cleaned hourly pollutants with ``src/features/compute_cpcb_aqi.py`` over the whole series per station, so the
24-hour window spans the CSV/OpenAQ boundary. Rows that backfill wrote are refreshed on re-run; rows written by any
other source are never overwritten.

    python -m src.live.backfill --dry-run          # builds everything, prints a summary, touches no database
    python -m src.live.backfill                    # loads (needs DATABASE_URL, the job_writer role)
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.compute_cpcb_aqi import (
    DEFAULT_RAW_DIR,
    POLLUTANT_COLUMNS,
    POLLUTANTS,
    _station_for_folder,
    compute_aqi,
)
from src.live import openaq
from src.live.qc import VALUE_COLUMNS, finish_hourly

CSV_SOURCE = "local_csv_2026"
OPENAQ_SOURCE = openaq.SOURCE_TAG
BACKFILL_SOURCES = (CSV_SOURCE, OPENAQ_SOURCE)
CSV_START, CSV_END = pd.Timestamp("2026-01-01 00:00"), pd.Timestamp("2026-08-31 23:00")
OPENAQ_START = pd.Timestamp("2026-09-01 00:00")
CSV_TO_COLUMN = {
    **POLLUTANT_COLUMNS,  # PM2.5, PM10, NO2, NH3, SO2, CO, Ozone
    "NOx (ppb)": "nox",
    "AT (°C)": "temperature",
    "RH (%)": "humidity",
    "WS (m/s)": "wind_speed",
    "SR (W/mt2)": "solar_radiation",
}


_finish = finish_hourly  # kept for existing callers/tests


def csv_history(
    raw_dir: Path = DEFAULT_RAW_DIR, start: pd.Timestamp = CSV_START, end: pd.Timestamp = CSV_END
) -> pd.DataFrame:
    parts = []
    for folder in sorted(os.listdir(raw_dir)):
        station = _station_for_folder(folder)
        files = list((Path(raw_dir) / folder / "Raw Data").glob(f"{start.year}_*_1H.csv")) if station else []
        for path in files:
            frame = pd.read_csv(path, parse_dates=["Timestamp"]).set_index("Timestamp")
            frame = frame.rename(columns=CSV_TO_COLUMN)
            frame = frame[~frame.index.duplicated(keep="last")].loc[start:end]
            if len(frame):
                parts.append(_finish(frame, station, CSV_SOURCE))
    return pd.concat(parts) if parts else pd.DataFrame()


def openaq_history(
    start: pd.Timestamp = OPENAQ_START, end: pd.Timestamp | None = None, cache: Path | None = None
) -> pd.DataFrame:
    end = end if end is not None else pd.Timestamp("2026-10-07 23:00")
    hours = pd.date_range(start, end, freq="h")
    raw_all: dict = {}
    if cache and cache.exists():
        raw_all = pickle.loads(cache.read_bytes())
        print(f"loaded cached OpenAQ downloads from {cache}", flush=True)
    parts = []
    for station, location_id in openaq.LOCATIONS.items():
        if station not in raw_all:
            raw_all[station] = {}
            for param, (sensor_id, _label) in openaq.live_sensors(location_id, station).items():
                raw_all[station][param] = openaq.fetch_15min(sensor_id, str(start), str(end + pd.Timedelta(minutes=59)))
                print(
                    f"fetched {station:16s} {param:17s} sensor {sensor_id}: {len(raw_all[station][param])} slots",
                    flush=True,
                )
        frame = openaq.hourly_frame(raw_all[station], hours)
        extra = openaq.UNVERIFIED_FLAG if station in openaq.ALIGNMENT_UNVERIFIED_2026 else None
        parts.append(_finish(frame, station, OPENAQ_SOURCE, extra))
    if cache:
        cache.write_bytes(pickle.dumps(raw_all))
    return pd.concat(parts) if parts else pd.DataFrame()


def aqi_history(readings: pd.DataFrame) -> pd.DataFrame:
    """Recompute the hourly CPCB AQI per station over the full series (CSV + OpenAQ together)."""
    raw = readings.reset_index().rename(columns={"hour": "Timestamp"})
    raw = raw[["station_id", "station_name", "Timestamp", *POLLUTANTS]]
    aqi = compute_aqi(raw.sort_values(["station_id", "Timestamp"]))
    aqi = aqi.dropna(subset=["aqi_value"])
    return aqi.rename(columns={"timestamp": "hour", "aqi_value": "aqi"})[["station_id", "station_name", "hour", "aqi"]]


def summarize(readings: pd.DataFrame, aqi: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (station, source), g in readings.groupby(["station_name", "source"]):
        rows.append(
            {
                "station": station,
                "source": source,
                "rows": len(g),
                "first": g.index.min(),
                "last": g.index.max(),
                "pm25_missing_%": round(100 * g.pm25.isna().mean(), 1),
                "nox_missing_%": round(100 * g.nox.isna().mean(), 1),
                "weather_missing_%": round(100 * g.temperature.isna().mean(), 1),
                "solar_missing_%": round(100 * g.solar_radiation.isna().mean(), 1),
                "qc_flagged_cells": int(sum(len([k for k in f if not k.startswith("_")]) for f in g.qc_flags)),
            }
        )
    table = pd.DataFrame(rows).sort_values(["station", "first"]).reset_index(drop=True)
    table["aqi_rows"] = table.station.map(aqi.groupby("station_name").size())
    return table


def _localize(index: pd.Index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index).tz_localize("Asia/Kolkata")


READING_COLUMNS = ["station_id", "ts", *VALUE_COLUMNS, "weather_source", "qc_flags", "source"]
UPSERT_READINGS = f"""
insert into aq.live_readings ({", ".join(READING_COLUMNS)}) values %s
on conflict (station_id, ts) do update set
  {", ".join(f"{c} = excluded.{c}" for c in READING_COLUMNS[2:])}, ingested_at = now()
where aq.live_readings.source in ('{CSV_SOURCE}', '{OPENAQ_SOURCE}')
"""
UPSERT_AQI = """
insert into aq.live_aqi (station_id, ts, aqi) values %s
on conflict (station_id, ts) do update set aqi = excluded.aqi, computed_at = now()
"""


def _clean(value):
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else value


def reading_tuples(readings: pd.DataFrame):
    from psycopg2.extras import Json

    ts = _localize(readings.index)
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
    ts = _localize(pd.DatetimeIndex(aqi.hour))
    for position, row in enumerate(aqi.itertuples()):
        yield int(row.station_id), ts[position].to_pydatetime(), float(row.aqi)


def load(readings: pd.DataFrame, aqi: pd.DataFrame, details: dict) -> None:
    from psycopg2.extras import execute_values

    from src.live.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into aq.job_runs (job, github_run) values ('backfill', %s) returning id",
            (os.environ.get("GITHUB_RUN_ID"),),
        )
        run_id = cur.fetchone()[0]
        try:
            execute_values(cur, UPSERT_READINGS, list(reading_tuples(readings)), page_size=1000)
            execute_values(cur, UPSERT_AQI, list(aqi_tuples(aqi)), page_size=2000)
        except Exception as exc:  # record the failure, then re-raise (message only, no connection details)
            cur.execute(
                "update aq.job_runs set status='failed', finished_at=clock_timestamp(), error=%s where id=%s",
                (type(exc).__name__, run_id),
            )
            conn.commit()
            raise
        cur.execute(
            "update aq.job_runs set status='success', finished_at=clock_timestamp(), rows_written=%s, details=%s where id=%s",
            (len(readings) + len(aqi), json.dumps(details, default=str), run_id),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="build and summarise; do not touch the database")
    parser.add_argument("--no-csv", action="store_true")
    parser.add_argument("--no-openaq", action="store_true")
    parser.add_argument(
        "--openaq-end", default="2026-10-07 23:00", help="last hour label to build from OpenAQ (local time)"
    )
    parser.add_argument("--cache", type=Path, default=None, help="pickle file for OpenAQ downloads (reused if present)")
    args = parser.parse_args()

    parts = []
    if not args.no_csv:
        parts.append(csv_history())
    if not args.no_openaq:
        parts.append(openaq_history(end=pd.Timestamp(args.openaq_end), cache=args.cache))
    readings = pd.concat([p for p in parts if len(p)])
    readings = readings.reset_index().sort_values(["station_id", "hour"]).set_index("hour")
    aqi = aqi_history(readings)
    summary = summarize(readings, aqi)
    pd.set_option("display.width", 220, "display.max_columns", 20)
    print(summary.to_string(index=False))
    print(f"\nreadings: {len(readings):,} rows | AQI: {len(aqi):,} rows")
    if args.dry_run:
        print("dry run: nothing written")
        return
    load(readings, aqi, {"summary": summary.to_dict(orient="records")})
    print("loaded")


if __name__ == "__main__":
    main()

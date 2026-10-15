"""data.gov.in "Real time Air Quality Index from various locations" as a live source (CPCB feed).

**NOT VERIFIED.** Everything below is built from third-party documentation of the resource, not from a real
response: from the development machine ``api.data.gov.in`` refuses connections, and the real fields, units, timestamp
format and hour convention are still to be read from the probe output (``src/live/probe_sources.py`` on a GitHub
runner). Until then ``verified`` is False and the ingest refuses this source unless explicitly allowed, so a wrong
guess cannot reach the database. Items to settle (all TODO(verify)):

* ``last_update`` format and time zone (documented as ``dd-mm-yyyy HH:MM:SS``; zone assumed IST);
* hour convention: does ``last_update`` = 14:00 describe the hour 13:00-14:00 or 14:00-15:00? Our label T means
  [T, T+1h); the assumption below (``HOUR_ENDS_AT_LAST_UPDATE``) is a guess;
* units (CO in mg/m3 and the rest in ug/m3 assumed, like the CSVs), and that ``pollutant_avg`` is the hourly mean;
* the exact station spellings (mapped through the project's folder names, which match "Name, Delhi - DPCC").

The feed is a *snapshot*: no history, no NOx, no weather. ``fetch`` therefore returns only the newest hour per
station and pollutant; a missed hour cannot be recovered from this source.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

from src.features.compute_cpcb_aqi import STATION_IDS, _station_for_folder
from src.live.sources.base import LiveSource, SourceUnavailable

RESOURCE_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
POLLUTANT_TO_COLUMN = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "NO2": "no2",
    "NH3": "nh3",
    "SO2": "so2",
    "CO": "co",
    "OZONE": "o3",
}
#: GUESS: last_update marks the END of the averaged hour, so the hour label T = last_update - 1h.
HOUR_ENDS_AT_LAST_UPDATE = True


def station_for_feed_name(name: str) -> str | None:
    """Map a feed station string to our canonical name (None for the other Delhi stations)."""
    name = (name or "").strip()
    direct = _station_for_folder(name)
    if direct:
        return direct
    head = name.split(",")[0].strip().lower()
    for ours in STATION_IDS:
        if head == ours.lower():
            return ours
    return None


def parse_records(records: list[dict]) -> pd.DataFrame:
    """Pivot feed records (one per station x pollutant) into one row per station and hour label."""
    rows = []
    for record in records:
        station = station_for_feed_name(record.get("station", ""))
        column = POLLUTANT_TO_COLUMN.get(str(record.get("pollutant_id", "")).strip().upper())
        if station is None or column is None:
            continue
        stamp = pd.to_datetime(record.get("last_update"), format="%d-%m-%Y %H:%M:%S", errors="coerce")
        value = pd.to_numeric(record.get("pollutant_avg"), errors="coerce")  # "NA" -> NaN
        if pd.isna(stamp):
            continue
        hour = stamp.floor("h") - (pd.Timedelta(hours=1) if HOUR_ENDS_AT_LAST_UPDATE else pd.Timedelta(0))
        rows.append({"station_name": station, "hour": hour, "column": column, "value": value})
    if not rows:
        return LiveSource.empty()
    long = pd.DataFrame(rows)
    wide = long.pivot_table(
        index=["station_name", "hour"], columns="column", values="value", aggfunc="last"
    ).reset_index()
    wide.columns.name = None
    return wide.reindex(columns=LiveSource.empty().columns)


class DataGovInSource(LiveSource):
    name = "data_gov_in"
    tag = "data.gov.in"
    verified = False
    missing = {"all stations": ["nox", "temperature", "humidity", "wind_speed", "solar_radiation"]}

    def __init__(self, api_key: str | None = None, session: Any = requests) -> None:
        self._key = (api_key if api_key is not None else os.environ.get("DATA_GOV_IN_API_KEY", "")).strip()
        self._session = session

    def fetch(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        if not self._key:
            raise SourceUnavailable("DATA_GOV_IN_API_KEY is not set")
        params = {"api-key": self._key, "format": "json", "limit": 500, "filters[city]": "Delhi"}
        try:
            response = self._session.get(RESOURCE_URL, params=params, timeout=40)
            response.raise_for_status()
            records = response.json().get("records", [])
        except (requests.RequestException, ValueError) as exc:
            # never include the exception text: requests puts the full URL (with the key) in it
            raise SourceUnavailable(f"data.gov.in request failed: {type(exc).__name__}") from None
        frame = parse_records(records)
        return frame[(frame["hour"] >= start) & (frame["hour"] <= end)].reset_index(drop=True)

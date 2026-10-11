"""OpenAQ v3 client and the conversions that make its data match the training CSVs.

Everything here was derived from a measured overlap with the project's raw CSVs
(``python -m src.live.openaq_overlap_check``, report in ``docs/TIER_3/openaq_overlap_check.md``):

* **Unit labels are wrong and are ignored.** NO2, SO2 and CO are labelled "ppb" but their numbers already
  equal our ug/m3 and mg/m3 columns; NOx is labelled "ppb" but is ppm (x1000). The conversion is by
  parameter, never from the label. The labels are *pinned* below: if OpenAQ corrects them,
  ``check_unit_labels`` raises ``UnitLabelChanged`` so a human re-verifies the numbers instead of the
  data silently changing meaning.
* **Hour convention.** OpenAQ stores 15-minute slots. The CSV value for hour T is the mean of the four slots
  starting at T (temperature and humidity: starting 15 minutes earlier). OpenAQ's own ``/hours`` endpoint
  averages differently and is not used.
* **Sensors.** The live sensor per parameter is the highest id; older ids stopped in 2018.
* **Dwarka-Sector 8** has no 2026 CSV, so its 2026 slot alignment could not be verified (Dec 2025 fits one
  15-minute step earlier). Its OpenAQ-derived rows carry ``{"_alignment": "unverified_2026"}``.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

if os.environ.get("FORCE_IPV4") == "1":  # dev networks whose IPv6/NAT64 route hangs
    import urllib3.util.connection as _conn

    _conn.HAS_IPV6 = False

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API = "https://api.openaq.org/v3"
SOURCE_TAG = "openaq"

# station name -> OpenAQ location id (CPCB provider, currently reporting; same-named 'caaqm'-provider
# locations ended in 2018-2022).
LOCATIONS = {
    "Anand Vihar": 235, "Bawana": 8472, "Dwarka-Sector 8": 6931, "ITO": 5613,
    "Jahangirpuri": 8235, "Punjabi Bagh": 50, "R K Puram": 17,
}
# OpenAQ parameter -> live_readings column
PARAM_TO_COLUMN = {
    "pm25": "pm25", "pm10": "pm10", "no2": "no2", "so2": "so2", "o3": "o3", "co": "co", "nox": "nox",
    "temperature": "temperature", "relativehumidity": "humidity", "wind_speed": "wind_speed",
}
# OpenAQ's unit label for the live sensor of each parameter, as observed at all 7 stations on 2026-10-11.
# These are NOT trusted as units (see module docstring); they are pinned only to detect upstream changes.
EXPECTED_UNIT_LABELS = {
    "pm25": "µg/m³", "pm10": "µg/m³", "no2": "ppb", "so2": "ppb", "o3": "µg/m³", "co": "ppb",
    "nox": "ppb", "temperature": "c", "relativehumidity": "%", "wind_speed": "m/s",
}
# value x factor = the unit our CSVs/training data use (derived from the data, not from the label)
UNIT_FACTOR = {"nox": 1000.0}
# start of the four-slot window relative to the hour label T, in minutes
SLOT_START_OFFSET_MIN = {"temperature": -15, "relativehumidity": -15}
# stations whose 2026 alignment could not be checked against a 2026 CSV
ALIGNMENT_UNVERIFIED_2026 = frozenset({"Dwarka-Sector 8"})
UNVERIFIED_FLAG = {"_alignment": "unverified_2026"}
# not available from OpenAQ at all
MISSING_FROM_OPENAQ = {"all stations": ["solar_radiation", "nh3"], "ITO": ["temperature", "humidity", "wind_speed"]}

CHUNK_DAYS = 9  # 9 days x 96 slots = 864 records, under the 1000-record page limit


class UnitLabelChanged(RuntimeError):
    """OpenAQ changed a sensor's unit label; the pinned conversion may no longer be right."""


def _headers() -> dict:
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is not set")
    return {"X-API-Key": key}


def get(path: str, **params) -> dict:
    """GET with polite rate limiting (60 requests/minute); the key is only ever sent as a header."""
    for _ in range(4):
        response = requests.get(f"{API}{path}", headers=_headers(), params=params, timeout=60)
        remaining = response.headers.get("x-ratelimit-remaining")
        reset = float(response.headers.get("x-ratelimit-reset", 30))
        if response.status_code == 429:
            time.sleep(reset + 1)
            continue
        response.raise_for_status()
        if remaining is not None and int(remaining) <= 1:
            time.sleep(reset + 1)
        return response.json()
    raise RuntimeError(f"rate limited on {path}")


def check_unit_labels(station: str, sensors: dict[str, tuple[int, str]]) -> None:
    changed = {p: (EXPECTED_UNIT_LABELS[p], unit) for p, (_, unit) in sensors.items() if unit != EXPECTED_UNIT_LABELS[p]}
    if changed:
        raise UnitLabelChanged(
            f"{station}: OpenAQ unit labels changed {changed} (pinned, observed). The numbers may have been "
            "rescaled: re-run `python -m src.live.openaq_overlap_check` and update UNIT_FACTOR / EXPECTED_UNIT_LABELS."
        )


def live_sensors(location_id: int, station: str = "") -> dict[str, tuple[int, str]]:
    """{parameter: (sensor_id, unit_label)} using the highest sensor id per parameter."""
    best: dict[str, tuple[int, str]] = {}
    for sensor in get(f"/locations/{location_id}/sensors")["results"]:
        name = sensor["parameter"]["name"]
        if name in PARAM_TO_COLUMN and sensor["id"] > best.get(name, (0, ""))[0]:
            best[name] = (sensor["id"], sensor["parameter"]["units"])
    check_unit_labels(station or str(location_id), best)
    return best


def fetch_15min(sensor_id: int, start: str, end: str) -> pd.DataFrame:
    """Raw 15-minute records (columns from, to, value) for local times [start, end], local naive timestamps."""
    start_ts = pd.Timestamp(start, tz="Asia/Kolkata") - pd.Timedelta(hours=2)
    end_ts = pd.Timestamp(end, tz="Asia/Kolkata") + pd.Timedelta(hours=2)
    frames, cursor = [], start_ts
    while cursor < end_ts:
        chunk_end = min(cursor + pd.Timedelta(days=CHUNK_DAYS), end_ts)
        rows = get(
            f"/sensors/{sensor_id}/measurements",
            datetime_from=cursor.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            datetime_to=chunk_end.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            limit=1000,
        )["results"]
        frames.append(pd.DataFrame({
            "from": [pd.Timestamp(r["period"]["datetimeFrom"]["local"]).tz_localize(None) for r in rows],
            "to": [pd.Timestamp(r["period"]["datetimeTo"]["local"]).tz_localize(None) for r in rows],
            "value": [r["value"] for r in rows],
        }))
        cursor = chunk_end
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["from", "to", "value"])
    return out.drop_duplicates("from", keep="last").sort_values("from").reset_index(drop=True)


def slots_to_hourly(raw: pd.DataFrame, hours: pd.DatetimeIndex, start_offset_min: int = 0,
                    factor: float = 1.0) -> pd.Series:
    """Value for each hour label T = mean of the four 15-minute slots starting at T + offset.

    An hour with fewer than four slots is NaN (never averaged from a partial hour).
    """
    grid = raw.drop_duplicates("from", keep="last").set_index("from")["value"].sort_index() * factor
    parts = np.vstack([
        grid.reindex(hours + pd.Timedelta(minutes=start_offset_min + k)).to_numpy(dtype=float) for k in (0, 15, 30, 45)
    ])
    complete = (~np.isnan(parts)).sum(axis=0) == 4
    return pd.Series(np.where(complete, np.nansum(parts, axis=0) / 4, np.nan), index=hours)


def hourly_frame(raw_by_param: dict[str, pd.DataFrame], hours: pd.DatetimeIndex) -> pd.DataFrame:
    """One station's hourly frame in live_readings column names, in training units."""
    data = {
        PARAM_TO_COLUMN[param]: slots_to_hourly(raw, hours, SLOT_START_OFFSET_MIN.get(param, 0), UNIT_FACTOR.get(param, 1.0))
        for param, raw in raw_by_param.items()
    }
    return pd.DataFrame(data, index=hours)

"""Google Air Quality API (airquality.googleapis.com), used only in shadow mode (``src/live/google_shadow.py``, ADR 0010).

What it returns, from a request for one coordinate:
  * pollutant concentrations: PM2.5 and PM10 in ug/m3 (whole numbers), NO2, O3, SO2, CO and NH3 in ppb;
  * the local Indian index ``ind_cpcb`` (NAQI) and, separately, the Universal AQI (``uaqi``), which is a different scale.
    The two are stored under their own keys and are never mixed: a Universal AQI is not a CPCB AQI.
The values are modelled on a grid at the coordinate, not measured by a monitor, which is what the gate tests.

Conversions to the units of ``aq.live_readings`` (ug/m3 for PM, NO2, SO2, O3; mg/m3 for CO) use 25 C and 1 atm
(24.45 L/mol), fixed here before any comparison. Unit labels are pinned: a label that changes raises ``UnitLabelChanged`` so a
human re-checks the numbers instead of the data silently changing meaning. Hours are on the UTC hour, so 11:00Z is 16:30 IST; the
shadow hour label is that instant floored to the IST hour (16:00) and the gate then tests offsets of -1, 0 and +1 hour.

The key is read from ``GOOGLE_AIR_QUALITY_API_KEY`` (env or ``.env``) and sent only as the ``X-Goog-Api-Key`` header, never in a
URL, a log line or an error. Every request is counted against a ``RequestBudget`` (billing is per request, per page for history).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "https://airquality.googleapis.com/v1"
SOURCE_TAG = "google"  # hourly current conditions, collected live
HISTORY_TAG = (
    "google_history"  # the 30-day history endpoint: kept apart, it can differ from what was published at the time
)
KST = "Asia/Kolkata"
LOCAL_AQI = {"regionCode": "IN", "aqi": "ind_cpcb"}  # NAQI (IN), the CPCB index
EXTRA = ["POLLUTANT_CONCENTRATION", "LOCAL_AQI"]
POLLUTANTS = ["pm25", "pm10", "no2", "so2", "co", "o3"]  # the columns of aq.shadow_readings
PAGE_SIZE = 168  # the largest page the API returns (checked 2026-10-25: pageSize 500 returns 168)
MAX_HISTORY_HOURS = 720

UG = "MICROGRAMS_PER_CUBIC_METER"
PPB = "PARTS_PER_BILLION"
EXPECTED_UNITS = {"pm25": UG, "pm10": UG, "no2": PPB, "so2": PPB, "o3": PPB, "co": PPB, "nh3": PPB}
MOLAR_VOLUME = 24.45  # L/mol at 25 C, 1 atm
MOLAR_MASS = {"no2": 46.0055, "so2": 64.066, "o3": 47.9982, "co": 28.010, "nh3": 17.031}


class UnitLabelChanged(RuntimeError):
    """Google changed a pollutant's unit; the pinned conversion may no longer be right."""


class GoogleError(RuntimeError):
    """A failed request. Carries the status only: the response body is never echoed."""


class BudgetExceeded(RuntimeError):
    """The run would spend more requests than it was allowed."""


class RequestBudget:
    """Counts every request attempt (retries included) and refuses the one past ``limit``."""

    def __init__(self, limit: int) -> None:
        self.limit, self.used = limit, 0

    def spend(self) -> None:
        if self.used >= self.limit:
            raise BudgetExceeded(f"request budget of {self.limit} reached")
        self.used += 1


def api_key() -> str:
    value = os.environ.get("GOOGLE_AIR_QUALITY_API_KEY")
    if not value and (REPO_ROOT / ".env").exists():
        for line in (REPO_ROOT / ".env").read_text().splitlines():
            if line.startswith("GOOGLE_AIR_QUALITY_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("\"'")
    if not value:
        raise SystemExit("GOOGLE_AIR_QUALITY_API_KEY is not set (env var or .env)")
    return value


def lookup(
    path: str,
    body: dict,
    key: str,
    budget: RequestBudget,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """POST ``body`` to ``path`` with retries on 429/5xx. Raises ``GoogleError(status)``; never includes the response body."""
    for attempt in range(4):
        budget.spend()
        response = post(f"{BASE_URL}{path}", json=body, headers={"X-Goog-Api-Key": key}, timeout=60)
        if response.status_code == 200:
            return response.json()
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            sleep(2 ** (attempt + 1))
            continue
        raise GoogleError(f"HTTP {response.status_code} from {path}")
    raise GoogleError(f"gave up on {path}")


def _body(lat: float, lon: float, **extra: Any) -> dict:
    return {
        "location": {"latitude": float(lat), "longitude": float(lon)},
        "extraComputations": EXTRA,
        "customLocalAqis": [LOCAL_AQI],
        "universalAqi": True,
        **extra,
    }


def current(lat: float, lon: float, key: str, budget: RequestBudget, **kw: Any) -> list[dict]:
    """The current hour as a one-element list of hour records (same shape as a history page)."""
    return [lookup("/currentConditions:lookup", _body(lat, lon), key, budget, **kw)]


def history(lat: float, lon: float, key: str, budget: RequestBudget, hours: int, **kw: Any) -> Iterator[dict]:
    """Hour records for the last ``hours`` hours (newest first), one request per page of ``PAGE_SIZE``."""
    if not 1 <= hours <= MAX_HISTORY_HOURS:
        raise ValueError(f"hours must be between 1 and {MAX_HISTORY_HOURS}")
    token = None
    while True:
        body = _body(lat, lon, hours=hours, pageSize=PAGE_SIZE, **({"pageToken": token} if token else {}))
        page = lookup("/history:lookup", body, key, budget, **kw)
        yield from page.get("hoursInfo", [])
        token = page.get("nextPageToken")
        if not token:
            return


def pages_needed(hours: int) -> int:
    return -(-hours // PAGE_SIZE)


def to_our_units(code: str, value: float) -> float:
    """Concentration in the unit of ``aq.live_readings``: ug/m3 (PM, NO2, SO2, O3, NH3) or mg/m3 (CO)."""
    if code in ("pm25", "pm10"):
        return float(value)
    ug_m3 = value * MOLAR_MASS[code] / MOLAR_VOLUME
    return ug_m3 / 1000.0 if code == "co" else ug_m3


def hour_label(date_time: str) -> pd.Timestamp:
    """The shadow hour label: the record's instant in IST, floored to the hour (naive, like ``live_readings`` labels)."""
    return pd.Timestamp(date_time).tz_convert(KST).floor("h").tz_localize(None)


def hour_row(station: str, info: dict) -> dict:
    """One shadow row from a current-conditions response or a history hour record."""
    raw: dict[str, Any] = {"indexes": {}, "pollutants": {}}
    row: dict[str, Any] = {pollutant: np.nan for pollutant in POLLUTANTS}
    for index in info.get("indexes", []):
        raw["indexes"][index["code"]] = index.get("aqi")  # 'ind_cpcb' (CPCB) and 'uaqi' (Universal) stay separate
    for pollutant in info.get("pollutants", []):
        code, concentration = pollutant["code"], pollutant.get("concentration") or {}
        if code not in EXPECTED_UNITS or concentration.get("value") is None:
            continue
        if concentration.get("units") != EXPECTED_UNITS[code]:
            raise UnitLabelChanged(f"{code}: expected {EXPECTED_UNITS[code]}, got {concentration.get('units')}")
        raw["pollutants"][code] = concentration["value"]
        if code in row:
            row[code] = to_our_units(code, concentration["value"])
    return {
        "station_name": station,
        "ts": hour_label(info["dateTime"]),
        "waqi_time": pd.Timestamp(info["dateTime"]).tz_convert(
            KST
        ),  # the source's own timestamp (column named for WAQI)
        "raw_iaqi": raw,
        **row,
    }

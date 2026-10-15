"""WAQI (api.waqi.info) station feeds, used only in shadow mode (``src/live/waqi_shadow.py``).

WAQI publishes US-EPA sub-indices (``iaqi``), not concentrations; the shadow job converts them back with ``src/live/epa_aqi.py``
and stores them in ``aq.shadow_readings``, a table the forecast job and the API never read. The token is read from
``WAQI_API_TOKEN`` (env or ``.env``) and never printed or logged.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "https://api.waqi.info"
SOURCE_TAG = "waqi_backconverted"
POLLUTANTS = ["pm25", "pm10", "no2", "so2", "co", "o3"]  # WAQI has no NH3
# our station -> (WAQI uid, how it was matched), chosen by name and distance to our station coordinates
MAPPING = {
    "Anand Vihar": (2553, "exact name"),
    "Bawana": (11267, "Pooth Khurd, Bawana; ~0.5 km"),
    "Dwarka-Sector 8": (10119, "NIMR, Sector 8, Dwarka; ~0.7 km"),
    "ITO": (
        10111,
        "NO ITO station on WAQI; nearest is Major Dhyan Chand National Stadium, ~1.9 km, a different monitor",
    ),
    "Jahangirpuri": (10113, "ITI Jahangirpuri; ~0.1 km"),
    "Punjabi Bagh": (2555, "exact name"),
    "R K Puram": (2556, "R.K. Puram"),
}


def token() -> str:
    value = os.environ.get("WAQI_API_TOKEN")
    if not value and (REPO_ROOT / ".env").exists():
        for line in (REPO_ROOT / ".env").read_text().splitlines():
            if line.startswith("WAQI_API_TOKEN="):
                value = line.split("=", 1)[1].strip().strip("\"'")
    if not value:
        raise SystemExit("WAQI_API_TOKEN is not set (env var or .env)")
    return value


def get(path: str, key: str, timeout: float = 30) -> dict:
    sep = "&" if "?" in path else "?"
    with urllib.request.urlopen(f"{BASE_URL}{path}{sep}token={key}", timeout=timeout) as response:  # noqa: S310 - fixed https host
        return json.load(response)


def fetch_feed(uid: int, key: str) -> dict:
    """The ``data`` object of one station feed; raises ValueError (message without the token) on a non-ok reply."""
    reply = get(f"/feed/@{uid}/", key)
    if reply.get("status") != "ok":
        raise ValueError(f"WAQI feed @{uid} returned status {reply.get('status')!r}")
    return reply["data"]

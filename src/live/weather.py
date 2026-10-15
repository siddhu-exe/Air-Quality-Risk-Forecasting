"""Recent hourly weather from Open-Meteo, used to fill inputs a live source cannot supply.

OpenAQ has no solar radiation (and no weather at ITO); data.gov.in has none at all. This fetches the last
days from the Open-Meteo forecast API (``past_days``), not the ERA5 archive endpoint, which lags by several days. It reuses
the project's retry/back-off helper (``src.features.exogenous_drivers._get_with_retry``), requests wind in m/s
(the API default is km/h, our station sensors report m/s) and sends one request per station, sequentially.

Caveats: these are model-analysis values, not on-site measurements; the hour label is the API's own (the same
approximation the D1 audit used with ERA5). Free tier, non-commercial, CC BY 4.0: credit Open-Meteo.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from src.features.exogenous_drivers import _get_with_retry
from src.live.load_stations import STATION_COORDS
from src.live.qc import FILLED_PREFIX, WEATHER_ALL

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
API_TO_COLUMN = {
    "temperature_2m": "temperature",
    "relative_humidity_2m": "humidity",
    "wind_speed_10m": "wind_speed",
    "shortwave_radiation": "solar_radiation",
}
FILL_TAG = FILLED_PREFIX + "open-meteo"


def fetch_recent(
    coords: dict[str, tuple[float, float]] = STATION_COORDS,
    past_days: int = 3,
    get=_get_with_retry,
    pause: float = 0.5,
    sleep=time.sleep,
) -> pd.DataFrame:
    """Hourly weather per station for the last ``past_days`` days. Columns: station_name, hour + the four weather columns."""
    parts = []
    for station, (lat, lon) in coords.items():
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(API_TO_COLUMN),
            "wind_speed_unit": "ms",
            "timezone": "Asia/Kolkata",
            "past_days": past_days,
            "forecast_days": 1,
        }
        payload = get(
            FORECAST_URL, params, label=f"open-meteo {station}", max_attempts=3, base_wait=3.0, timeout=30
        ).json()["hourly"]
        frame = pd.DataFrame(payload).rename(columns={"time": "hour", **API_TO_COLUMN})
        frame["hour"] = pd.to_datetime(frame["hour"])
        frame.insert(0, "station_name", station)
        parts.append(frame[["station_name", "hour", *API_TO_COLUMN.values()]])
        sleep(pause)
    return pd.concat(parts, ignore_index=True)


def fill_missing(frame: pd.DataFrame, weather: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Fill only the missing weather cells of ``frame`` (rows: station_name, hour, ...). Returns (frame, per-row flags).

    Station-sensor values are never replaced. Row order and index are preserved.
    """
    out = frame.copy()
    flags: list[dict] = [dict() for _ in range(len(out))]
    if out.empty or weather.empty:
        return out, flags
    lookup = weather.drop_duplicates(["station_name", "hour"]).set_index(["station_name", "hour"])
    keys = pd.MultiIndex.from_arrays([out["station_name"], out["hour"]])
    matched = lookup.reindex(keys)
    for column in WEATHER_ALL:
        if column not in out:
            out[column] = np.nan
        replacement = matched[column].to_numpy()
        fill = out[column].isna().to_numpy() & ~pd.isna(replacement)
        out.loc[fill, column] = replacement[fill]
        for position in np.flatnonzero(fill):
            flags[position][column] = FILL_TAG
    return out, flags

"""
exogenous_drivers.py
=====================
Fetch and attach exogenous drivers for the AQI models (improvement plan T2.4):

  * **Meteorology** — Open-Meteo ERA5 archive (wind u/v, boundary-layer height,
    temperature, humidity, precipitation, solar radiation) at each station.
  * **Fires** — NASA FIRMS VIIRS active-fire counts in a Punjab/Haryana bounding
    box, aggregated per day and lagged 1-3 days.

Network access is required, so this runs in the Colab notebook (or any machine
with internet). Everything is keyed on (station_name, timestamp) and merged onto
the existing feature matrix without changing any raw data.

Usage
-----
    python -m src.features.exogenous_drivers --start 2024-01-01 --end 2025-12-31
    # optional fires (needs a free NASA FIRMS MAP_KEY):
    FIRMS_MAP_KEY=xxxx python -m src.features.exogenous_drivers --fires

Rate limits: Open-Meteo is a free shared API (Colab IPs are shared, so its limits trip easily).
Requests are therefore sequential (one station, one calendar year at a time) with a pause between
them, 429/5xx responses are retried with the wait the server asks for, and every finished chunk is
cached in ``data/processed/exogenous_cache/`` so reruns make no requests and an interrupted run
resumes. If an hourly/daily quota is exhausted the script stops with a clear message (the cache is
kept); rerun later. ``--refresh`` ignores the cache.

Outputs
-------
    data/processed/exogenous_weather.parquet
    data/processed/exogenous_fires.parquet        (only with --fires)
    data/processed/exogenous_cache/*.parquet      (per station-year weather chunks)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"
CACHE_DIR = PROCESSED / "exogenous_cache"
KST = "Asia/Kolkata"
REQUEST_PAUSE_S = 2.0  # polite gap between successful requests
CACHE_MIN_AGE_DAYS = 10  # recent ERA5 days are still being filled in; do not cache chunks that touch them

# Approximate CAAQMS coordinates (WGS84); used only to sample gridded weather.
STATION_COORDS = {
    "Anand Vihar": (28.6469, 77.3164),
    "Bawana": (28.7974, 77.0338),
    "Dwarka-Sector 8": (28.5710, 77.0721),
    "ITO": (28.6289, 77.2410),
    "Jahangirpuri": (28.7256, 77.1623),
    "Punjabi Bagh": (28.6740, 77.1310),
    "R K Puram": (28.5644, 77.1766),
}

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_SOURCE = "VIIRS_SNPP_NRT"
PUNJAB_HARYANA_BBOX = (73.5, 28.5, 77.8, 32.5)  # west, south, east, north

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "boundary_layer_height",
    "shortwave_radiation",
    "surface_pressure",
]


class RateLimitExhausted(RuntimeError):
    """An hourly/daily API quota is used up; retrying in a few minutes will not help."""


def _error_reason(response: requests.Response) -> str:
    try:
        return str(response.json().get("reason", "")) or response.text[:200]
    except ValueError:
        return response.text[:200]


def _get_with_retry(url: str, params: dict | None = None, *, label: str = "request",
                    max_attempts: int = 6, base_wait: float = 5.0, timeout: int = 120,
                    sleep=time.sleep) -> requests.Response:
    """GET with retry/backoff on network errors, 429 and 5xx; fail fast on other 4xx."""
    last = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last = repr(exc)
            wait = min(60.0, base_wait * 2 ** (attempt - 1))
            print(f"  {label}: network error ({last}); retry {attempt}/{max_attempts} in {wait:.0f}s", flush=True)
            sleep(wait)
            continue
        if response.status_code == 200:
            return response
        reason = _error_reason(response)
        if response.status_code == 429 or 500 <= response.status_code < 600:
            low = reason.lower()
            if "hourly" in low or "daily" in low:
                raise RateLimitExhausted(
                    f"{label}: {reason} Finished chunks are cached; rerun this cell later "
                    "(hourly quotas reset within the hour, daily ones at midnight UTC).")
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isdigit():
                wait = float(retry_after)
            elif "minut" in low or response.status_code == 429:
                wait = 65.0
            else:
                wait = min(120.0, base_wait * 2 ** (attempt - 1))
            wait += random.uniform(0.0, 3.0)
            last = f"HTTP {response.status_code} {reason}"
            print(f"  {label}: {last}; retry {attempt}/{max_attempts} in {wait:.0f}s", flush=True)
            sleep(wait)
            continue
        response.raise_for_status()
    raise RuntimeError(f"{label}: gave up after {max_attempts} attempts (last: {last})")


def _year_chunks(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Calendar-year (start, end) date strings covering [start_date, end_date]."""
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    chunks = []
    for year in range(start.year, end.year + 1):
        s = max(start, pd.Timestamp(year=year, month=1, day=1))
        e = min(end, pd.Timestamp(year=year, month=12, day=31))
        chunks.append((str(s.date()), str(e.date())))
    return chunks


def _cache_path(station: str, chunk_start: str, chunk_end: str) -> Path:
    key = hashlib.md5(",".join(HOURLY_VARS).encode()).hexdigest()[:8]
    slug = "".join(ch if ch.isalnum() else "_" for ch in station).strip("_")
    return CACHE_DIR / f"{slug}_{chunk_start}_{chunk_end}_{key}.parquet"


def _fetch_station_chunk(station: str, lat: float, lon: float, chunk_start: str, chunk_end: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": chunk_start,
        "end_date": chunk_end,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Asia/Kolkata",
    }
    response = _get_with_retry(OPEN_METEO_URL, params, label=f"{station} {chunk_start}..{chunk_end}")
    frame = pd.DataFrame(response.json()["hourly"]).rename(columns={"time": "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["station_name"] = station
    return frame


def fetch_open_meteo_weather(start_date: str, end_date: str, refresh: bool = False) -> pd.DataFrame:
    """Hourly ERA5 weather for every station: sequential, throttled, retried and cached per station-year."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    recent_cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=CACHE_MIN_AGE_DAYS)
    frames, fetched, cached = [], 0, 0
    for station, (lat, lon) in STATION_COORDS.items():
        for chunk_start, chunk_end in _year_chunks(start_date, end_date):
            path = _cache_path(station, chunk_start, chunk_end)
            if path.exists() and not refresh:
                frame = pd.read_parquet(path)
                cached += 1
                print(f"  cached  {station} {chunk_start}..{chunk_end}: {len(frame):,} rows", flush=True)
            else:
                frame = _fetch_station_chunk(station, lat, lon, chunk_start, chunk_end)
                fetched += 1
                print(f"  fetched {station} {chunk_start}..{chunk_end}: {len(frame):,} rows", flush=True)
                if pd.Timestamp(chunk_end) < recent_cutoff:
                    frame.to_parquet(path, index=False)
                time.sleep(REQUEST_PAUSE_S)
            frames.append(frame)
    print(f"weather chunks: {fetched} fetched, {cached} from cache", flush=True)
    weather = pd.concat(frames, ignore_index=True)

    direction = np.deg2rad(weather["wind_direction_10m"])
    weather["wind_u"] = -weather["wind_speed_10m"] * np.sin(direction)
    weather["wind_v"] = -weather["wind_speed_10m"] * np.cos(direction)
    return weather.sort_values(["station_name", "timestamp"]).reset_index(drop=True)


def _firms_window(map_key: str, start: pd.Timestamp, days: int) -> pd.DataFrame:
    west, south, east, north = PUNJAB_HARYANA_BBOX
    area = f"{west},{south},{east},{north}"
    url = f"{FIRMS_URL}/{map_key}/{FIRMS_SOURCE}/{area}/{days}/{start.date()}"
    response = _get_with_retry(url, label=f"FIRMS {start.date()}")
    from io import StringIO
    text = response.text
    if "acq_date" not in text:
        return pd.DataFrame(columns=["acq_date", "count"])
    fires = pd.read_csv(StringIO(text))
    return fires


def fetch_firms_daily_fires(start_date: str, end_date: str, map_key: str,
                            window_days: int = 5) -> pd.DataFrame:
    """Daily VIIRS active-fire counts in the Punjab/Haryana box (chunked requests)."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    frames = []
    cursor = start
    while cursor <= end:
        try:
            chunk = _firms_window(map_key, cursor, window_days)
        except requests.HTTPError as exc:  # surfaced with context for the user
            raise RuntimeError(f"FIRMS request failed for {cursor.date()}: {str(exc).replace(map_key, '***')}") from None
        if len(chunk):
            frames.append(chunk[["acq_date"]])
        cursor += pd.Timedelta(days=window_days)
        time.sleep(0.5)
    if not frames:
        daily = pd.DataFrame(columns=["date", "fire_count"])
    else:
        all_fires = pd.concat(frames, ignore_index=True)
        all_fires["date"] = pd.to_datetime(all_fires["acq_date"])
        daily = (
            all_fires.groupby(all_fires["date"].dt.normalize())
            .size()
            .rename("fire_count")
            .reset_index()
            .rename(columns={"date": "date"})
        )
    full = pd.DataFrame({"date": pd.date_range(start.normalize(), end.normalize(), freq="D")})
    full = full.merge(daily, on="date", how="left").fillna({"fire_count": 0})
    full["fire_count"] = full["fire_count"].astype(int)
    for lag in (1, 2, 3):
        full[f"fire_lag_{lag}d"] = full["fire_count"].shift(lag)
    return full


def attach_exogenous(features_path: Path, weather: pd.DataFrame, fires: pd.DataFrame | None,
                     output_path: Path) -> pd.DataFrame:
    """Merge weather (causal + oracle t+24) and fires onto the feature matrix."""
    frame = pd.read_parquet(features_path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None)
    weather = weather.rename(columns={"timestamp": "timestamp"})
    weather["timestamp"] = pd.to_datetime(weather["timestamp"])

    base_vars = ["temperature_2m", "relative_humidity_2m", "precipitation",
                 "wind_u", "wind_v", "boundary_layer_height", "shortwave_radiation"]
    frame = frame.merge(
        weather[["station_name", "timestamp"] + base_vars],
        on=["station_name", "timestamp"], how="left",
    )

    # Causal lags/rolls of the same-hour weather, and an "oracle" value at t+24.
    parts = []
    for station, group in frame.groupby("station_name"):
        group = group.sort_values("timestamp").copy()
        for var in base_vars:
            group[f"wx_{var}"] = group[var]
            group[f"wx_{var}_roll24"] = group[var].rolling(24, min_periods=6).mean()
            group[f"wx_{var}_t24_oracle"] = group[var].shift(-24)  # labelled oracle
        parts.append(group)
    frame = pd.concat(parts, ignore_index=True)

    if fires is not None and len(fires):
        fires = fires.copy()
        fires["date"] = pd.to_datetime(fires["date"]).dt.tz_localize(None).dt.normalize()
        frame["date"] = frame["timestamp"].dt.normalize()
        frame = frame.merge(fires, on="date", how="left").drop(columns=["date"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch/attach exogenous drivers")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--features", type=Path, default=PROCESSED / "features_extended.parquet")
    parser.add_argument("--output", type=Path, default=PROCESSED / "features_exogenous.parquet")
    parser.add_argument("--fires", action="store_true", help="also fetch NASA FIRMS fire counts")
    parser.add_argument("--refresh", action="store_true", help="ignore the weather cache and refetch")
    args = parser.parse_args()

    print("Fetching Open-Meteo ERA5 weather...")
    weather = fetch_open_meteo_weather(args.start, args.end, refresh=args.refresh)
    weather.to_parquet(PROCESSED / "exogenous_weather.parquet", index=False)
    print(f"Wrote {PROCESSED / 'exogenous_weather.parquet'}")

    fires = None
    if args.fires:
        map_key = os.environ.get("FIRMS_MAP_KEY")
        if not map_key:
            raise SystemExit("Set FIRMS_MAP_KEY (free key from firms.modaps.eosdis.nasa.gov) to fetch fires.")
        print("Fetching NASA FIRMS fire counts...")
        fires = fetch_firms_daily_fires(args.start, args.end, map_key)
        fires.to_parquet(PROCESSED / "exogenous_fires.parquet", index=False)
        print(f"Wrote {PROCESSED / 'exogenous_fires.parquet'}")

    frame = attach_exogenous(args.features, weather, fires, args.output)
    print(f"Wrote {args.output} ({frame.shape[0]:,} rows, {frame.shape[1]} cols)")


if __name__ == "__main__":
    main()

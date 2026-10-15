"""Cell-level quality control for hourly readings, shared by the backfill and the live ingest.

Same rules as the ETL (``etl/schemas.py``): instrument sentinels and values outside physical bounds
are set to NULL *per cell* (never dropping the row), and the reason is kept in ``qc_flags``.
One extra rule guards against silent unit changes upstream: values above a plausibility ceiling
(set from the maxima in the project's own CSVs, with headroom) are nullified and flagged
``implausible``, and a batch where many values of one column are implausible raises, because that
pattern means a unit or scale changed, not that the air got dirtier.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from etl.schemas import PHYSICAL_BOUNDS, SENTINEL_VALUES
from src.features.compute_cpcb_aqi import STATION_IDS

VALUE_COLUMNS = [
    "pm25", "pm10", "no2", "nox", "nh3", "so2", "co", "o3",
    "temperature", "humidity", "wind_speed", "solar_radiation",
]

# live_readings column -> key in etl.schemas.PHYSICAL_BOUNDS
_ETL_KEY = {
    "pm25": "pm25", "pm10": "pm10", "no2": "no2_ugm3", "nox": "nox_ppb", "nh3": "nh3_ugm3",
    "so2": "so2_ugm3", "co": "co_mgm3", "o3": "ozone_ugm3", "humidity": "rh_pct",
    "wind_speed": "ws_ms", "solar_radiation": "sr_wm2",
}

# Ceilings well above the largest value in the 2024-2026 CSVs (e.g. PM2.5 998, NOx 499, CO 9.76),
# so real extremes pass but a 1000x scale error does not.
PLAUSIBLE_MAX = {
    "pm25": 1500.0, "pm10": 2000.0, "no2": 1000.0, "nox": 1000.0, "nh3": 1000.0, "so2": 1000.0,
    "co": 50.0, "o3": 1000.0, "temperature": 55.0, "humidity": 100.0, "wind_speed": 60.0,
    "solar_radiation": 1500.0,
}
MIN_BY_COLUMN = {"temperature": -5.0}  # Delhi never goes below this; a unit mix-up would
MAX_IMPLAUSIBLE_SHARE = 0.25


class ImplausibleBatch(RuntimeError):
    """Raised when a large share of a column is implausible: a probable unit/scale change upstream."""


def apply_qc(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Return (cleaned frame, per-row flag dicts). Input is not modified."""
    clean = frame.copy()
    flags: list[dict] = [dict() for _ in range(len(clean))]
    for column in (c for c in VALUE_COLUMNS if c in clean):
        values = pd.to_numeric(clean[column], errors="coerce")
        reasons = pd.Series("", index=clean.index, dtype=object)

        reasons[values.isin(SENTINEL_VALUES)] = "sentinel"
        low, high = PHYSICAL_BOUNDS.get(_ETL_KEY.get(column, ""), (None, None))
        if low is not None:
            reasons[(values < low) & (reasons == "")] = "bounds"
        if high is not None:
            reasons[(values > high) & (reasons == "")] = "bounds"
        if column in MIN_BY_COLUMN:
            reasons[(values < MIN_BY_COLUMN[column]) & (reasons == "")] = "implausible"
        reasons[(values > PLAUSIBLE_MAX[column]) & (reasons == "")] = "implausible"

        bad = reasons != ""
        clean[column] = values.mask(bad)
        for position in np.flatnonzero(bad.to_numpy()):
            flags[position][column] = reasons.iloc[position]
    return clean, flags


def check_batch(frame: pd.DataFrame, flags: list[dict], max_share: float = MAX_IMPLAUSIBLE_SHARE) -> None:
    """Raise ImplausibleBatch if too many *present* values of one column were flagged implausible."""
    for column in (c for c in VALUE_COLUMNS if c in frame):
        implausible = sum(1 for row in flags if row.get(column) == "implausible")
        present = int(frame[column].notna().sum()) + implausible
        if present >= 20 and implausible / present > max_share:
            raise ImplausibleBatch(
                f"{implausible} of {present} '{column}' values are implausible: "
                "a unit or scale change upstream is likely; re-verify against the CSVs before loading"
            )


WEATHER_COLUMNS = ["temperature", "humidity", "wind_speed"]
WEATHER_ALL = WEATHER_COLUMNS + ["solar_radiation"]
FILLED_PREFIX = "filled:"


def finish_hourly(frame: pd.DataFrame, station: str, source: str, extra_flags: dict | None = None,
                  row_flags: list[dict] | None = None) -> pd.DataFrame:
    """QC one station's hourly frame (index = hour label), tag it, and drop hours with no usable value.

    ``extra_flags`` is merged into every row's ``qc_flags``; ``row_flags`` (aligned with the frame's rows) are
    merged per row, e.g. ``{"solar_radiation": "filled:open-meteo"}``. ``weather_source`` is ``station`` when the
    weather values come from the station sensors, ``open-meteo`` when all of them were filled from Open-Meteo,
    ``mixed`` otherwise, NULL when there is no weather at all.

    Output columns: station_id, station_name, the VALUE_COLUMNS, weather_source, qc_flags, source.
    """
    frame = frame.copy()
    for column in VALUE_COLUMNS:
        if column not in frame:
            frame[column] = np.nan
    frame = frame[VALUE_COLUMNS].astype(float)
    clean, flags = apply_qc(frame)
    check_batch(clean, flags)
    for position in range(len(flags)):
        if extra_flags:
            flags[position].update(extra_flags)
        if row_flags:
            # a filled value that QC then rejected is no longer filled
            flags[position].update({k: v for k, v in row_flags[position].items() if k not in flags[position]})
    filled = np.array([[str(f.get(c, "")).startswith(FILLED_PREFIX) for c in WEATHER_ALL] for f in flags]).reshape(len(flags), len(WEATHER_ALL))
    present = clean[WEATHER_ALL].notna().to_numpy()
    n_present = present.sum(axis=1)
    n_filled = (filled & present).sum(axis=1)
    source_label = np.where(n_present == 0, None, np.where(n_filled == 0, "station", np.where(n_filled == n_present, "open-meteo", "mixed")))
    out = clean.copy()
    out.insert(0, "station_id", STATION_IDS[station])
    out["station_name"] = station
    out["weather_source"] = source_label
    out["qc_flags"] = flags
    out["source"] = source
    out.index.name = "hour"
    return out[out[VALUE_COLUMNS].notna().any(axis=1)]

"""Chronological split helpers shared by the Tier 2 scripts.

Windows (Asia/Kolkata), identical to the frozen models so results stay comparable:
  train: everything before 2025-09-01 (extended matrix starts 2024-01-01)
  val:   2025-09-01 .. 2025-10-31
  test:  2025-11-01 .. 2025-12-31

Targets are ``x.shift(-h)`` (h up to 24), so the label of a training row issued
in the last ``h`` hours before a window starts is observed *inside* that window.
``purge_train_tail`` removes those rows (an embargo) so no training label
overlaps the evaluation window.
"""

from __future__ import annotations

import pandas as pd

KST = "Asia/Kolkata"
VAL_START = pd.Timestamp("2025-09-01", tz=KST)
VAL_END = pd.Timestamp("2025-10-31 23:59:59", tz=KST)
TEST_START = pd.Timestamp("2025-11-01", tz=KST)
TEST_END = pd.Timestamp("2025-12-31 23:59:59", tz=KST)
EMBARGO_HOURS = 24  # the longest forecast horizon used in the project

META_COLUMNS = {"station_id", "station_name", "timestamp", "split", "aqi_source"}
# Raw/cyclical calendar columns. The project removed them from the AQI hybrid
# (trees cannot extrapolate across seasons they have not seen). The Tier 2
# gradient-boosting scripts treat "with/without calendar" as a validation-selected
# choice rather than silently including them.
CALENDAR_FEATURES = {
    "hour",
    "day_of_week",
    "month",
    "day_of_year",
    "is_weekend",
    "sin_hour",
    "cos_hour",
    "sin_dow",
    "cos_dow",
    "sin_month",
    "cos_month",
    "sin_doy",
    "cos_doy",
    "is_winter",
    "is_summer",
    "is_monsoon",
    "is_post_monsoon",
}


def to_kst(ts: pd.Series) -> pd.Series:
    ts = pd.to_datetime(ts)
    return ts.dt.tz_localize(KST) if ts.dt.tz is None else ts.dt.tz_convert(KST)


def assign_split(timestamps: pd.Series) -> pd.Series:
    """Label rows ``train`` / ``val`` / ``test`` (index aligned to the input)."""
    ts = to_kst(timestamps)
    split = pd.Series("train", index=timestamps.index)
    split[(ts >= VAL_START) & (ts <= VAL_END)] = "val"
    split[(ts >= TEST_START) & (ts <= TEST_END)] = "test"
    return split


def purge_train_tail(
    frame: pd.DataFrame,
    train_end: pd.Timestamp,
    embargo_hours: int = EMBARGO_HOURS,
    time_col: str = "timestamp",
) -> pd.DataFrame:
    """Rows issued before ``train_end - embargo`` so no label reaches ``train_end``."""
    ts = to_kst(frame[time_col])
    return frame[ts < (train_end - pd.Timedelta(hours=embargo_hours))]


def training_rows(frame: pd.DataFrame, embargo_hours: int = EMBARGO_HOURS) -> pd.DataFrame:
    """The ``train`` split with the embargo applied against the validation start."""
    train = frame[frame["split"] == "train"]
    return purge_train_tail(train, VAL_START, embargo_hours)


def model_feature_columns(frame: pd.DataFrame, drop_calendar: bool = True) -> list[str]:
    """Numeric, non-target, non-meta columns (optionally without calendar features)."""
    skip = set(META_COLUMNS) | (CALENDAR_FEATURES if drop_calendar else set())
    return [
        c
        for c in frame.columns
        if c not in skip and not c.startswith("target_") and pd.api.types.is_numeric_dtype(frame[c])
    ]

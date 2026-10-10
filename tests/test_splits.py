"""Tests for the chronological split + embargo helpers (src/models/splits.py)."""
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.models.splits import (  # noqa: E402
    KST,
    VAL_START,
    assign_split,
    purge_train_tail,
    training_rows,
)


def _hourly(start, end):
    idx = pd.date_range(start, end, freq="h", tz=KST)
    return pd.DataFrame({"timestamp": idx})


def test_assign_split_boundaries():
    frame = _hourly("2025-08-31 22:00", "2025-11-01 02:00")
    frame["split"] = assign_split(frame["timestamp"])
    ts = frame["timestamp"]
    assert (frame.loc[ts < VAL_START, "split"] == "train").all()
    assert frame.loc[ts == pd.Timestamp("2025-09-01 00:00", tz=KST), "split"].iat[0] == "val"
    assert frame.loc[ts == pd.Timestamp("2025-10-31 23:00", tz=KST), "split"].iat[0] == "val"
    assert frame.loc[ts == pd.Timestamp("2025-11-01 00:00", tz=KST), "split"].iat[0] == "test"


def test_assign_split_accepts_naive_timestamps():
    naive = pd.Series(pd.to_datetime(["2025-08-31 23:00", "2025-09-01 00:00"]))
    assert assign_split(naive).tolist() == ["train", "val"]


def test_embargo_removes_labels_that_reach_the_eval_window():
    frame = _hourly("2025-08-25", "2025-08-31 23:00")
    frame["split"] = "train"
    horizon = 24
    kept = training_rows(frame, embargo_hours=horizon)
    # label of a kept row is observed at t + horizon and must precede the val window
    label_time = kept["timestamp"] + pd.Timedelta(hours=horizon)
    assert (label_time <= VAL_START).all()
    # and the embargo removes exactly `horizon` hours of rows
    assert len(frame) - len(kept) == horizon


def test_embargo_zero_keeps_everything():
    frame = _hourly("2025-08-25", "2025-08-31 23:00")
    out = purge_train_tail(frame, VAL_START, embargo_hours=0)
    assert len(out) == len(frame)
    assert np.all(out["timestamp"] < VAL_START)

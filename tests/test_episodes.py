"""Synthetic tests for the episode hit-rate / lead-time metric (T1.3).

These build toy frames with a known episode and known forecasts and assert the
expected hit/miss status and lead time, so the metric's time alignment is pinned
down by a test instead of by comments.
"""

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src" / "models"))

from phase_7_classification import episode_detection_report  # noqa: E402

TZ = "Asia/Kolkata"


def _severe_targets(issues, start, end):
    targets = issues + pd.Timedelta(hours=6)
    in_window = (targets >= pd.Timestamp(start, tz=TZ)) & (targets <= pd.Timestamp(end, tz=TZ))
    return np.where(in_window, 420.0, 300.0)


def test_known_lead_time_model_and_persistence():
    """Station 1: model alerts at t=04:00 (lead 2h), persistence at t=05:00 (lead 1h)."""
    issues = pd.date_range(pd.Timestamp("2025-11-01 00:00", tz=TZ), periods=24, freq="h")
    df = pd.DataFrame({"station_id": 1, "station_name": "S1", "timestamp": issues})
    df["y_true"] = _severe_targets(issues, "2025-11-01 06:00", "2025-11-01 12:00")
    df["y_pred"] = 300.0
    df.loc[df.index[4], "y_pred"] = 420.0  # issue 04:00 -> target 10:00
    df["naive_pred"] = 300.0
    df.loc[df.index[5], "naive_pred"] = 420.0  # issue 05:00 -> target 11:00

    rep = episode_detection_report(df, "6h", "y_true", "y_pred", "naive_pred")

    assert set(rep["model"]) == {"final", "persistence"}
    final = rep[rep["model"] == "final"].iloc[0]
    persist = rep[rep["model"] == "persistence"].iloc[0]
    assert final["detection"] == "hit"
    assert final["lead_time_hours"] == 2.0
    assert persist["detection"] == "hit"
    assert persist["lead_time_hours"] == 1.0


def test_miss_when_no_alert_fires():
    issues = pd.date_range(pd.Timestamp("2025-11-01 00:00", tz=TZ), periods=24, freq="h")
    df = pd.DataFrame({"station_id": 2, "station_name": "S2", "timestamp": issues})
    df["y_true"] = _severe_targets(issues, "2025-11-01 06:00", "2025-11-01 12:00")
    df["y_pred"] = 300.0
    df["naive_pred"] = 250.0

    rep = episode_detection_report(df, "6h", "y_true", "y_pred", "naive_pred")

    assert (rep["detection"] == "miss").all()
    assert (rep["lead_time_hours"] == 0.0).all()


def test_legacy_tolerance_flags_pre_episode_alert():
    """An alert targeting 1h before the episode start is a miss at tol=0, hit at tol=12."""
    issues = pd.date_range(pd.Timestamp("2025-10-31 20:00", tz=TZ), periods=24, freq="h")
    df = pd.DataFrame({"station_id": 3, "station_name": "S3", "timestamp": issues})
    df["y_true"] = _severe_targets(issues, "2025-11-01 06:00", "2025-11-01 12:00")
    df["y_pred"] = 300.0
    df.loc[df["timestamp"] == pd.Timestamp("2025-10-31 23:00", tz=TZ), "y_pred"] = 420.0
    df["naive_pred"] = 300.0

    rep = episode_detection_report(df, "6h", "y_true", "y_pred", "naive_pred")
    final = rep[rep["model"] == "final"].iloc[0]

    assert final["detection"] == "miss"
    assert final["lead_time_hours"] == 0.0
    assert final["detection_tol12"] == "hit"
    assert final["lead_time_hours_tol12"] == 7.0

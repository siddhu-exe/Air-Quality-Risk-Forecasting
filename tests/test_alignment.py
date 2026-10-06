"""Alignment tests for the feature builder.

Pins down two invariants the whole pipeline depends on:
  1. targets look FORWARD by exactly the horizon (``target_aqi_24h[t] == aqi[t+24]``);
  2. engineered features look only BACKWARD (a spike at time T cannot change any
     non-target feature for rows with timestamp < T).
"""
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src" / "features"))

from build_features import engineer_station_features  # noqa: E402

TZ = "Asia/Kolkata"
SPIKE = 99999.0


def _toy(hours=72, start="2025-06-01 00:00"):
    idx = pd.date_range(pd.Timestamp(start, tz=TZ), periods=hours, freq="h")
    aqi = pd.DataFrame({"timestamp": idx, "aqi_value": np.arange(hours, dtype=float)})
    caaqms = pd.DataFrame({
        "timestamp": idx,
        "pm25": np.arange(hours, dtype=float) * 2.0,
        "pm10": np.arange(hours, dtype=float) * 3.0,
    })
    return idx, aqi, caaqms


def _features(aqi, caaqms):
    return engineer_station_features(1, "S1", caaqms, aqi).set_index("timestamp").sort_index()


def test_target_aqi_24h_is_exactly_future_aqi():
    _, aqi, caaqms = _toy()
    f = _features(aqi, caaqms)
    expected = f["aqi_curr"].shift(-24)
    both = expected.notna() & f["target_aqi_24h"].notna()
    assert both.sum() >= 24
    assert np.allclose(f.loc[both, "target_aqi_24h"], expected[both])


def test_target_aqi_1h_and_6h_are_exactly_future_aqi():
    _, aqi, caaqms = _toy()
    f = _features(aqi, caaqms)
    for horizon, col in ((1, "target_aqi_1h"), (6, "target_aqi_6h")):
        expected = f["aqi_curr"].shift(-horizon)
        both = expected.notna() & f[col].notna()
        assert both.sum() >= 6
        assert np.allclose(f.loc[both, col], expected[both]), col


def test_lags_use_only_past_values():
    _, aqi, caaqms = _toy()
    f = _features(aqi, caaqms)
    for source, lag_col in (("aqi_curr", "aqi_lag_1h"), ("pm25_curr", "pm25_lag_1h")):
        expected = f[source].shift(1)
        both = expected.notna() & f[lag_col].notna()
        assert both.sum() >= 24
        assert np.allclose(f.loc[both, lag_col], expected[both]), lag_col


def test_future_spike_does_not_leak_into_earlier_features():
    idx, aqi, caaqms = _toy()
    spike_time = idx[40]

    caaqms_spiked = caaqms.copy()
    caaqms_spiked.loc[caaqms_spiked["timestamp"] == spike_time, "pm25"] = SPIKE
    aqi_spiked = aqi.copy()
    aqi_spiked.loc[aqi_spiked["timestamp"] == spike_time, "aqi_value"] = SPIKE

    base = _features(aqi, caaqms)
    spiked = _features(aqi_spiked, caaqms_spiked)

    feature_cols = [
        c for c in base.columns
        if not c.startswith("target_") and c not in ("station_id", "station_name")
    ]
    before = base.index < spike_time
    assert before.sum() >= 24
    assert np.allclose(
        base.loc[before, feature_cols].to_numpy(dtype=float),
        spiked.loc[before, feature_cols].to_numpy(dtype=float),
        equal_nan=True,
    )
    # The spike must be visible exactly at its own timestamp, not earlier.
    assert spiked.loc[spike_time, "aqi_curr"] == SPIKE
    assert spiked.loc[spike_time, "pm25_curr"] == SPIKE

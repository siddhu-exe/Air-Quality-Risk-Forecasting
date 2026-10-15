"""The recomputed AQI at hour t may use only raw hourly values <= t, and the window-update baseline must be exact."""

import numpy as np
import pandas as pd
import pytest

from src.evaluation.window_update_baseline import gain_importance, window_update_estimate
from src.features.compute_cpcb_aqi import POLLUTANTS, compute_aqi, hourly_aqi_series

HOURS = 240
CUT = 150  # hours with index <= CUT must not change when later raw values are perturbed


def _raw(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2025-01-01", periods=HOURS, freq="h")
    data = {
        "pm25": rng.uniform(20, 300, HOURS),
        "pm10": rng.uniform(40, 400, HOURS),
        "no2": rng.uniform(10, 150, HOURS),
        "so2": rng.uniform(5, 60, HOURS),
        "nh3": rng.uniform(5, 100, HOURS),
        "co": rng.uniform(0.2, 4, HOURS),
        "o3": rng.uniform(5, 120, HOURS),
    }
    frame = pd.DataFrame({"Timestamp": index, "station_id": 1, "station_name": "S", **data})
    assert set(POLLUTANTS) <= set(frame.columns)
    return frame


def _aqi(raw: pd.DataFrame, method: str) -> pd.Series:
    return compute_aqi(raw, method=method).set_index("timestamp")["aqi_value"]


@pytest.mark.parametrize("method", ["rolling_subindex_mean", "concentration_mean"])
def test_aqi_at_t_ignores_later_raw_values(method):
    raw = _raw()
    base = _aqi(raw, method)
    perturbed = raw.copy()
    later = perturbed.index > CUT
    perturbed.loc[later, POLLUTANTS] = perturbed.loc[later, POLLUTANTS] * 4
    perturbed.loc[perturbed.index > CUT + 20, POLLUTANTS] = np.nan
    changed = _aqi(perturbed, method)
    upto = base.index[: CUT + 1]
    pd.testing.assert_series_equal(base.loc[upto], changed.loc[upto])
    assert not np.allclose(base.iloc[CUT + 1 :].fillna(-1), changed.iloc[CUT + 1 :].fillna(-1))


def _single_driver(pollutant: str, level: float) -> pd.DataFrame:
    """Hourly frame where ``pollutant`` alone sets the AQI (the others sit low but valid)."""
    index = pd.date_range("2025-01-01", periods=HOURS, freq="h")
    frame = pd.DataFrame({p: 1.0 for p in POLLUTANTS}, index=index)
    frame["pm25"], frame["pm10"], frame["no2"] = 5.0, 10.0, 5.0
    frame[pollutant] = level + np.arange(HOURS) % 7
    return frame


@pytest.mark.parametrize("pollutant, level", [("co", 3.0), ("o3", 150.0)])
def test_eight_hour_smoothing_is_trailing_and_exactly_eight(pollutant, level):
    """The hourly AQI at t moves with the raw value at t-7 and not with the one at t-8 (CO and O3 use 8h means)."""
    t = 200
    frame = _single_driver(pollutant, level)
    base = hourly_aqi_series(frame).iloc[t]
    inside, outside, future = frame.copy(), frame.copy(), frame.copy()
    inside.iloc[t - 7, inside.columns.get_loc(pollutant)] += 5
    outside.iloc[t - 8, outside.columns.get_loc(pollutant)] += 5
    future.iloc[t + 1, future.columns.get_loc(pollutant)] += 50
    assert hourly_aqi_series(inside).iloc[t] != base
    assert hourly_aqi_series(outside).iloc[t] == base
    assert hourly_aqi_series(future).iloc[t] == base


def test_aqi_is_the_trailing_24h_mean_of_the_hourly_aqi():
    raw = _raw()
    hourly = hourly_aqi_series(raw.set_index("Timestamp")[POLLUTANTS])
    expected = hourly.rolling(24, min_periods=16).mean()
    np.testing.assert_allclose(_aqi(raw, "rolling_subindex_mean").to_numpy(), expected.to_numpy(), equal_nan=True)


def test_hourly_aqi_ignores_the_future():
    raw = _raw().set_index("Timestamp")[POLLUTANTS]
    base = hourly_aqi_series(raw)
    shifted = raw.copy()
    shifted.iloc[CUT + 1 :] = shifted.iloc[CUT + 1 :] * 5
    pd.testing.assert_series_equal(base.iloc[: CUT + 1], hourly_aqi_series(shifted).iloc[: CUT + 1])


@pytest.mark.parametrize("horizon", [1, 6, 23, 24])
def test_window_update_is_exact_when_the_future_is_flat(horizon):
    rng = np.random.default_rng(1)
    hourly = pd.Series(rng.uniform(50, 300, 120), index=pd.date_range("2025-01-01", periods=120, freq="h"))
    t = 70
    truth_series = hourly.copy()
    truth_series.iloc[t + 1 : t + horizon + 1] = hourly.iloc[t]  # the future stays at the current value
    truth = truth_series.rolling(24, min_periods=16).mean().iloc[t + horizon]
    assert window_update_estimate(hourly, horizon).iloc[t] == pytest.approx(truth)


def test_window_update_needs_the_current_hour_and_enough_history():
    hourly = pd.Series(np.arange(100.0, 160.0), index=pd.date_range("2025-01-01", periods=60, freq="h"))
    hourly.iloc[40] = np.nan
    estimate = window_update_estimate(hourly, 1)
    assert np.isnan(estimate.iloc[40])
    assert not np.isnan(estimate.iloc[41])
    assert estimate.iloc[:14].isna().all()  # < 16 valid hours in the target window


def test_gain_importance_parses_a_lightgbm_dump():
    text = "feature_names=a b c\nsplit_feature=0 1\nsplit_gain=3 1\n\nsplit_feature=0\nsplit_gain=4\n"
    shares = gain_importance(text)
    assert shares["a"] == pytest.approx(7 / 8)
    assert shares["b"] == pytest.approx(1 / 8)
    assert "c" not in shares

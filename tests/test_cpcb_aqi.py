"""Tests for the CPCB AQI reconstruction (src/features/compute_cpcb_aqi.py)."""

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.features.compute_cpcb_aqi import (  # noqa: E402
    _validity_mask,
    compute_aqi,
    sub_index,
)


def test_pm25_subindex_breakpoints():
    # CPCB PM2.5 bands: 0->0, 30->50, 60->100, 90->200, 120->300, 250->400, 500->500.
    got = sub_index("pm25", [0, 30, 60, 90, 120, 250, 500])
    assert np.allclose(got, [0, 50, 100, 200, 300, 400, 500])


def test_co_subindex_uses_mg_per_m3_bands():
    # CO bands in mg/m3: 1->50, 2->100, 10->200, 34->400.
    got = sub_index("co", [1, 2, 10, 34])
    assert np.allclose(got, [50, 100, 200, 400])


def test_subindex_interpolates_and_handles_missing():
    got = sub_index("pm25", [45, np.nan])
    assert np.isclose(got[0], 75.0)  # halfway between 30->50 and 60->100
    assert np.isnan(got[1])


def test_validity_requires_three_pollutants_and_a_pm():
    sub = pd.DataFrame(
        {
            "pm25": [90.0, np.nan],
            "pm10": [np.nan, np.nan],
            "no2": [40.0, 40.0],
            "so2": [40.0, 40.0],
            "nh3": [np.nan, np.nan],
            "co": [np.nan, np.nan],
            "o3": [np.nan, np.nan],
        }
    )
    mask = _validity_mask(sub)
    # Row 0: pm25 + no2 + so2 = 3 pollutants and has PM -> valid.
    # Row 1: only no2 + so2 = 2 pollutants and no PM -> invalid.
    assert mask.tolist() == [True, False]


def _synthetic_raw(hours=60):
    idx = pd.date_range("2025-01-01 00:00", periods=hours, freq="h")
    return pd.DataFrame(
        {
            "station_id": 3,
            "station_name": "Anand Vihar",
            "Timestamp": idx,
            "pm25": 60.0,
            "pm10": 100.0,
            "no2": 40.0,
            "so2": 40.0,
            "nh3": 200.0,
            "co": 1.0,
            "o3": 50.0,
        }
    )


def test_compute_aqi_constant_input_matches_max_subindex():
    raw = _synthetic_raw()
    out = compute_aqi(raw)
    # max sub-index = pm25(60)=100, pm10(100)=100, nh3(200)=50 -> 100
    assert np.allclose(out["aqi_value"].dropna().unique(), [100.0])


def test_compute_aqi_zero_when_pm_missing():
    raw = _synthetic_raw()
    raw["pm25"] = np.nan
    raw["pm10"] = np.nan
    out = compute_aqi(raw)
    assert out["aqi_value"].isna().all()

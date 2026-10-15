"""Pins the US-EPA conversion used to read WAQI ``iaqi`` back as concentrations (src/live/epa_aqi.py)."""
import numpy as np
import pytest

from src.live.epa_aqi import AQI_MAX, POLLUTANTS, from_aqi, roundtrip, to_aqi

# (concentration ug/m3, AQI) copied from the PM2.5 conversion table on https://aqicn.org/calculator/
WAQI_PM25_TABLE = [(0, 0), (1, 4), (5, 21), (10, 42), (12, 50), (13, 52), (20, 67), (30, 88), (35, 99), (36, 101), (40, 111),
                   (50, 136), (60, 152), (70, 158), (80, 163), (100, 173), (120, 184), (150, 200), (151, 201), (180, 230), (199, 249)]


@pytest.mark.parametrize("conc,expected", WAQI_PM25_TABLE)
def test_pm25_matches_the_published_waqi_table(conc, expected):
    assert to_aqi("pm25", [conc])[0] == expected


def test_cap_at_500_and_nan_passthrough():
    assert to_aqi("pm25", [900.0])[0] == AQI_MAX
    assert from_aqi("pm25", [600.0])[0] == pytest.approx(500.5)
    assert np.isnan(to_aqi("co", [np.nan])[0]) and np.isnan(from_aqi("co", [np.nan])[0])


@pytest.mark.parametrize("pollutant", POLLUTANTS)
def test_monotonic_and_within_half_an_aqi_unit_of_the_input(pollutant):
    top = from_aqi(pollutant, [AQI_MAX])[0]
    grid = np.linspace(0, top, 2000)
    index = to_aqi(pollutant, grid)
    assert (np.diff(index) >= 0).all()
    # the inverse of a rounded index lands within half an index step of the original concentration
    back = roundtrip(pollutant, grid)
    widest = max(np.diff(from_aqi(pollutant, [0, 50, 100, 150, 200, 300, 400, 500])) / np.array([50, 50, 50, 50, 100, 100, 100]))
    assert np.abs(back - grid).max() <= 0.5 * widest + 1e-9


def test_unit_conversion_is_pinned_at_25c():
    # CO: 1.0 mg/m3 -> 0.873 ppm -> AQI 0.873/4.5*50 = 9.7 -> 10 ; 8-hour table, ppm
    assert to_aqi("co", [1.0])[0] == 10
    # NO2: 40 ug/m3 = 21.3 ppb -> 21.3/54*50 = 19.7 -> 20
    assert to_aqi("no2", [40.0])[0] == 20
    # O3: 100 ug/m3 = 0.0509 ppm -> 0.0509/0.055*50 = 46.3 -> 46
    assert to_aqi("o3", [100.0])[0] == 46
    # SO2: 20 ug/m3 = 7.63 ppb -> 7.63/36*50 = 10.6 -> 11
    assert to_aqi("so2", [20.0])[0] == 11


def test_roundtrip_is_idempotent_on_the_second_pass():
    x = np.array([3.3, 17.8, 61.2, 213.0, 420.0])
    once = roundtrip("pm10", x)
    assert np.allclose(roundtrip("pm10", once), once)

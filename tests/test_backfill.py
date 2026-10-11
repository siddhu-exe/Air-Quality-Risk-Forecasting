"""Backfill logic with synthetic CSV / OpenAQ data. No network, no database."""
import numpy as np
import pandas as pd
import pytest

from src.live import backfill, openaq


def _write_csv(root, station_folder, hours=48, sentinel_at=None):
    folder = root / station_folder / "Raw Data"
    folder.mkdir(parents=True)
    idx = pd.date_range("2026-08-30 00:00", periods=hours, freq="h")
    frame = pd.DataFrame({"Timestamp": idx, "PM2.5 (µg/m³)": 100.0, "PM10 (µg/m³)": 180.0, "NO2 (µg/m³)": 40.0,
                          "NH3 (µg/m³)": 10.0, "SO2 (µg/m³)": 8.0, "CO (mg/m³)": 1.2, "Ozone (µg/m³)": 30.0, "NOx (ppb)": 60.0,
                          "AT (°C)": 30.0, "RH (%)": 55.0, "WS (m/s)": 1.5, "SR (W/mt2)": 200.0})
    if sentinel_at is not None:
        frame.loc[sentinel_at, "PM2.5 (µg/m³)"] = -9999
    frame.to_csv(folder / "2026_raw_data_hourly_x_1H.csv", index=False)


def test_csv_history_tags_source_clips_to_window_and_flags_sentinels(tmp_path):
    _write_csv(tmp_path, "R K Puram, Delhi - DPCC", sentinel_at=3)
    got = backfill.csv_history(tmp_path)
    assert set(got.source) == {backfill.CSV_SOURCE}
    assert got.index.max() <= backfill.CSV_END                     # 48 h from Aug 30 00:00 would reach Sep 1; clipped
    assert (got.station_id == 9).all()
    row = got.iloc[3]
    assert np.isnan(row.pm25) and row.qc_flags == {"pm25": "sentinel"}
    assert got.iloc[4].pm25 == 100.0 and got.iloc[4].qc_flags == {}          # the rest of the row and the series survive
    assert (got.weather_source == "station").all()


def test_missing_csv_station_is_simply_absent(tmp_path):
    _write_csv(tmp_path, "R K Puram, Delhi - DPCC")
    assert set(backfill.csv_history(tmp_path).station_name) == {"R K Puram"}


def _fake_openaq(monkeypatch, with_weather=True):
    start = pd.Timestamp("2026-08-31 22:00")
    slots = pd.date_range(start, periods=4 * 8, freq="15min")
    def raw(value):
        return pd.DataFrame({"from": slots, "to": slots + pd.Timedelta(minutes=15), "value": value})
    def sensors(location_id, station=""):
        base = {"pm25": (1, "µg/m³"), "pm10": (2, "µg/m³"), "no2": (3, "ppb"), "nox": (4, "ppb"), "co": (5, "ppb")}
        if with_weather and station != "ITO":
            base["temperature"] = (6, "c")
        return base
    values = {1: 120.0, 2: 200.0, 3: 45.0, 4: 0.09, 5: 1.1, 6: 28.0}
    monkeypatch.setattr(openaq, "live_sensors", sensors)
    monkeypatch.setattr(openaq, "fetch_15min", lambda sensor_id, start, end: raw(values[sensor_id]))


def test_openaq_history_applies_nox_factor_flags_dwarka_and_leaves_ito_without_weather(monkeypatch):
    _fake_openaq(monkeypatch)
    got = backfill.openaq_history(pd.Timestamp("2026-09-01 00:00"), pd.Timestamp("2026-09-01 04:00"))
    assert set(got.source) == {"openaq"}
    one = got[got.station_name == "R K Puram"].iloc[0]
    assert one.nox == pytest.approx(90.0) and one.no2 == 45.0 and one.pm25 == 120.0     # 0.09 ppm -> 90 ppb; no2 label ignored
    assert one.qc_flags == {}
    dwarka = got[got.station_name == "Dwarka-Sector 8"]
    assert all(f.get("_alignment") == "unverified_2026" for f in dwarka.qc_flags)
    assert not any("_alignment" in f for f in got[got.station_name != "Dwarka-Sector 8"].qc_flags)
    ito = got[got.station_name == "ITO"]
    assert ito.temperature.isna().all() and ito.weather_source.isna().all()
    assert got[got.station_name == "Bawana"].weather_source.eq("station").all()
    assert got.solar_radiation.isna().all() and got.nh3.isna().all()                    # not available from OpenAQ


def test_aqi_is_recomputed_over_the_csv_openaq_boundary(tmp_path, monkeypatch):
    _write_csv(tmp_path, "R K Puram, Delhi - DPCC", hours=48)
    csv = backfill.csv_history(tmp_path, end=pd.Timestamp("2026-08-31 23:00"))
    _fake_openaq(monkeypatch)
    oaq = backfill.openaq_history(pd.Timestamp("2026-09-01 00:00"), pd.Timestamp("2026-09-01 04:00"))
    readings = pd.concat([csv, oaq[oaq.station_name == "R K Puram"]])
    aqi = backfill.aqi_history(readings)
    assert aqi.hour.max() >= pd.Timestamp("2026-09-01 00:00")           # the series continues past the source boundary
    assert aqi.aqi.between(0, 500).all()


def test_refresh_never_overwrites_rows_from_other_sources():
    sql = backfill.UPSERT_READINGS
    assert "on conflict (station_id, ts) do update" in sql
    assert f"source in ('{backfill.CSV_SOURCE}', '{backfill.OPENAQ_SOURCE}')" in sql      # the guard that protects live rows
    assert "delete" not in sql.lower()


def test_rows_with_no_usable_value_are_dropped():
    frame = pd.DataFrame({"pm25": [np.nan, 5.0]}, index=pd.date_range("2026-09-01", periods=2, freq="h"))
    out = backfill._finish(frame, "Bawana", "openaq")
    assert len(out) == 1 and out.pm25.iloc[0] == 5.0

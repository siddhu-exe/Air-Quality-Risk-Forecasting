"""The shared, pure feature path (src.features.build_features.compute_feature_frame). Synthetic data only."""

import numpy as np
import pandas as pd
import pytest

from src.features import build_features as bf

TZ = "Asia/Kolkata"
STATIONS = {3: "Anand Vihar", 4: "Bawana", 9: "R K Puram"}
START = pd.Timestamp("2026-01-01 00:00", tz=TZ)
END = pd.Timestamp("2026-01-14 23:00", tz=TZ)


def _synthetic(seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(START, END, freq="h")
    stations = pd.DataFrame({"station_id": list(STATIONS), "station_name": list(STATIONS.values()), "city": "Delhi"})
    c_parts, a_parts = [], []
    for sid in STATIONS:
        n = len(idx)
        base = 150 + 60 * np.sin(np.arange(n) / 24 * 2 * np.pi) + rng.normal(0, 10, n)
        c_parts.append(
            pd.DataFrame(
                {
                    "station_id": sid,
                    "timestamp": idx,
                    "pm25": base,
                    "pm10": base * 1.8,
                    "no2": base / 3,
                    "nox": base / 2,
                    "so2": base / 10,
                    "co": base / 100,
                    "o3": base / 4,
                    "temperature": 20 + rng.normal(0, 2, n),
                    "humidity": 60 + rng.normal(0, 5, n),
                    "wind_speed": np.abs(rng.normal(1.5, 0.5, n)),
                    "solar_radiation": np.abs(rng.normal(100, 20, n)),
                }
            )
        )
        a_parts.append(
            pd.DataFrame(
                {"station_id": sid, "timestamp": idx, "aqi_value": base.clip(0, 500), "aqi_source": "recomputed"}
            )
        )
    return stations, pd.concat(c_parts, ignore_index=True), pd.concat(a_parts, ignore_index=True)


def _frame(**overrides):
    stations, caaqms, aqi = _synthetic()
    caaqms = caaqms.assign(**overrides) if overrides else caaqms
    return bf.compute_feature_frame(stations, caaqms, aqi, START, END, START + pd.Timedelta(days=9), END)


def test_target_and_lags_are_aligned_in_time():
    frame = _frame()
    one = frame[frame.station_id == 3].set_index("timestamp")
    t = one.index[50]
    assert one.loc[t, "target_aqi_24h"] == one.loc[t + pd.Timedelta(hours=24), "aqi_curr"]
    assert one.loc[t, "aqi_lag_24h"] == one.loc[t - pd.Timedelta(hours=24), "aqi_curr"]
    assert (
        one.loc[t, "aqi_lag_168h"] == one.loc[t - pd.Timedelta(hours=168), "aqi_curr"]
        if t - pd.Timedelta(hours=168) in one.index
        else True
    )


def test_window_filter_and_row_order():
    frame = _frame()
    assert frame.timestamp.min() >= START + pd.Timedelta(days=9)
    assert (frame.groupby("station_id").timestamp.apply(lambda s: s.is_monotonic_increasing)).all()


def test_masking_nox_changes_only_nox_derived_columns():
    base, masked = _frame(), _frame(nox=np.nan)
    changed = [
        c for c in base.columns if not base[c].equals(masked[c]) and not (base[c].isna() & masked[c].isna()).all()
    ]
    assert changed and all(c.startswith("nox_") for c in changed), changed


def test_cross_station_features_exclude_self():
    frame = _frame()
    t = frame.timestamp.iloc[100]
    at_t = frame[frame.timestamp == t].set_index("station_id")
    others = at_t.aqi_lag_1h.drop(3).mean()
    assert at_t.loc[3, "network_mean_aqi_lag_1h"] == pytest.approx(others)


def test_assemble_wrapper_writes_the_same_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "REPORTS_DIR", tmp_path)
    stations, caaqms, aqi = _synthetic()
    window_start = START + pd.Timedelta(days=9)
    pure = bf.compute_feature_frame(stations, caaqms, aqi, START, END, window_start, END)
    out = tmp_path / "f.parquet"
    written = bf.assemble_feature_matrix(stations, caaqms, aqi, START, END, window_start, END, out)
    pd.testing.assert_frame_equal(pure, written)
    pd.testing.assert_frame_equal(pure, pd.read_parquet(out))

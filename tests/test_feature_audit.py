"""Scenario logic of the D1 feature-availability audit. Synthetic data; no models, no network."""
import numpy as np
import pandas as pd

from src.evaluation import feature_availability_audit as audit

TZ = "Asia/Kolkata"


def _caaqms():
    idx = pd.date_range("2025-09-01", periods=4, freq="h", tz=TZ)
    rows = []
    for name, sid in (("ITO", 6), ("Bawana", 4)):
        rows.append(pd.DataFrame({"station_id": sid, "station_name": name, "timestamp": idx, "nox": 100.0, "pm25": 50.0,
                                  "temperature": 30.0, "humidity": 40.0, "wind_speed": 2.0, "solar_radiation": 500.0}))
    return pd.concat(rows, ignore_index=True).sample(frac=1, random_state=0)   # unsorted, non-contiguous index


def _weather():
    idx = pd.date_range("2025-09-01", periods=4, freq="h", tz=TZ)
    return pd.concat([pd.DataFrame({"station_name": n, "timestamp": idx, "temperature_2m": 25.0, "relative_humidity_2m": 60,
                                    "wind_speed_10m": 7.2, "shortwave_radiation": 300.0}) for n in ("ITO", "Bawana")], ignore_index=True)


def test_baseline_changes_nothing():
    base = _caaqms()
    pd.testing.assert_frame_equal(audit.apply_scenario(base, {}, False, None), base)


def test_openaq_gaps_unfilled_masks_solar_everywhere_and_weather_only_at_ito():
    out = audit.apply_scenario(_caaqms(), audit.OPENAQ_GAPS, False, None)
    assert out.solar_radiation.isna().all()
    ito, bawana = out[out.station_name == "ITO"], out[out.station_name == "Bawana"]
    assert ito[["temperature", "humidity", "wind_speed"]].isna().all().all()
    assert bawana[["temperature", "humidity", "wind_speed"]].notna().all().all()
    assert out.nox.notna().all()                       # NOx is available from OpenAQ


def test_filled_values_come_from_open_meteo_and_wind_is_converted_from_kmh_to_ms():
    out = audit.apply_scenario(_caaqms(), audit.OPENAQ_GAPS, True, _weather())
    ito = out[out.station_name == "ITO"]
    assert (ito.temperature == 25.0).all() and (ito.humidity == 60).all()
    assert ito.wind_speed.eq(2.0).all()                # 7.2 km/h = 2.0 m/s
    assert (out.solar_radiation == 300.0).all()
    bawana = out[out.station_name == "Bawana"]
    assert (bawana.temperature == 30.0).all() and (bawana.wind_speed == 2.0).all()   # untouched station sensors


def test_datagovin_scenario_masks_nox_and_all_weather_and_never_fills_nox():
    out = audit.apply_scenario(_caaqms(), audit.DATAGOVIN_GAPS, True, _weather())
    assert out.nox.isna().all()
    assert (out.temperature == 25.0).all() and out.pm25.eq(50.0).all()


def test_input_is_not_modified():
    base = _caaqms()
    before = base.copy()
    audit.apply_scenario(base, audit.DATAGOVIN_GAPS, True, _weather())
    pd.testing.assert_frame_equal(base, before)


def test_evaluate_reports_zero_delta_for_identical_predictions_and_a_clear_degradation_otherwise():
    rng = np.random.default_rng(0)
    n = 600
    frame = pd.DataFrame({"timestamp": pd.date_range("2025-09-01", periods=n, freq="h", tz=TZ),
                          "aqi_curr": rng.uniform(100, 300, n)})
    frame["target_aqi_24h"] = frame.aqi_curr + rng.normal(0, 10, n)
    good = frame["target_aqi_24h"].to_numpy() + rng.normal(0, 3, n)
    same = audit.evaluate(frame, good, good, "target_aqi_24h")
    assert same["delta_mae_vs_baseline"] == 0 and same["delta_mae_ci_lo"] == 0 == same["delta_mae_ci_hi"]
    assert same["skill_mae"] > 0.5
    worse = audit.evaluate(frame, good + 25.0, good, "target_aqi_24h")
    assert worse["delta_mae_vs_baseline"] > 20 and worse["delta_mae_ci_lo"] > 0


def test_scenarios_are_defined_for_every_case_the_user_listed():
    assert "solar_radiation" in audit.OPENAQ_GAPS["*"] and set(audit.OPENAQ_GAPS["ITO"]) == {"temperature", "humidity", "wind_speed"}
    assert "nox" in audit.DATAGOVIN_GAPS["*"] and {"temperature", "humidity", "wind_speed", "solar_radiation"} <= set(audit.DATAGOVIN_GAPS["*"])


def test_audit_refuses_test_window_rows():
    assert audit.VAL_END < audit.TEST_START


def test_report_lists_both_row_sets(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "OUT_DIR", tmp_path)
    row = dict(horizon="24h", scenario="baseline", description="d", mae=1.0, mae_persistence=2.0, skill_mae=0.5, delta_mae_vs_baseline=0.0,
               skill_ci_lo=0.4, skill_ci_hi=0.6, delta_mae_ci_lo=0.0, delta_mae_ci_hi=0.0)
    table = pd.DataFrame([{**row, "row_set": "all", "n": 9590}, {**row, "row_set": "strict", "n": 9422}])
    audit.write_report(table, {"share_of_cells_equal": 1.0, "rows": 1, "columns": 1})
    text = (tmp_path / "feature_availability_audit.md").read_text()
    assert "| 24h | all | baseline | 9,590 |" in text and "| 24h | strict | baseline | 9,422 |" in text

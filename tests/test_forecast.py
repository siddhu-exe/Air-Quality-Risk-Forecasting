"""Forecast job logic on synthetic data: no database, no model files needed except the hash check."""

import json

import numpy as np
import pandas as pd
import pytest

from src.live import forecast, forecast_store, serving
from src.live import models as model_mod
from src.live.forecast import KST

ISSUE = pd.Timestamp("2026-10-07 12:00", tz=KST)
GATE = {"max_core_missing_share": 0.22}


def fake_models():
    core = (
        [f"aqi_lag_{h}h" for h in (1, 24)]
        + [f"pm25_lag_{h}h" for h in (1, 24)]
        + ["pm10_lag_1h", "no2_lag_1h", "so2_lag_1h", "co_lag_1h", "o3_lag_1h"]
    )
    names = core + ["nox_lag_1h", "temp_curr", "solar_rad_curr", "station_ITO"]
    return serving.Serving(
        specs=[serving.SPECS["aqi_1h"], serving.SPECS["aqi_6h"], serving.SPECS["aqi_24h"]],
        loaded={},
        features={"aqi_6h": names, "aqi_24h": core},
    )


def history(hours=200, station="ITO", **missing):
    """Feature-row history (rows with an AQI) ending at ISSUE, plus the row at ISSUE."""
    stamps = pd.date_range(end=ISSUE, periods=hours, freq="h")
    frame = pd.DataFrame({"timestamp": stamps, "station_name": station, "aqi_curr": 150.0})
    for column in fake_models().features["aqi_6h"]:
        if not column.startswith("station_") and column != "aqi_curr":
            frame[column] = 1.0
    for column, value in missing.items():
        frame[column] = value
    return frame


def verdict(frame=None, latest=ISSUE, row=True, gate=GATE, **kw):
    frame = history() if frame is None else frame
    at = frame.iloc[-1] if row else None
    return forecast.assess_station("ITO", at, frame, latest, ISSUE, fake_models(), gate, **kw)


# ------------------------------------------------------------------ inputs
def test_filled_weather_is_masked_for_the_models_but_station_values_stay():
    readings = pd.DataFrame(
        {
            "temperature": [30.0, 31.0],
            "solar_radiation": [500.0, 600.0],
            "qc_flags": [{"solar_radiation": "filled:open-meteo"}, {"temperature": "filled:open-meteo"}],
        }
    )
    masked = forecast.mask_filled_weather(readings, "none")
    assert np.isnan(masked.solar_radiation.iloc[0]) and masked.temperature.iloc[0] == 30.0
    assert np.isnan(masked.temperature.iloc[1]) and masked.solar_radiation.iloc[1] == 600.0
    assert readings.solar_radiation.iloc[0] == 500.0  # the input is not modified
    kept = forecast.mask_filled_weather(readings, "open-meteo")
    assert kept.solar_radiation.iloc[0] == 500.0


def test_to_inputs_returns_the_feature_builders_shapes_and_names_stations():
    ts = pd.date_range("2026-10-07 10:00", periods=3, freq="h", tz=KST)
    readings = pd.DataFrame(
        {
            "station_id": 6,
            "ts": ts,
            "pm25": [1.0, 2.0, 3.0],
            "qc_flags": [{}, {}, {}],
            "weather_source": None,
            "source": "openaq",
        }
    )
    aqi = pd.DataFrame({"station_id": 6, "ts": ts, "aqi": [100.0, 110.0, 120.0]})
    caaqms, aqi_df = forecast.to_inputs(readings, aqi)
    assert (
        set(caaqms.station_name) == {"ITO"}
        and str(caaqms.timestamp.dt.tz) == KST
        and "nox" in caaqms
        and "ts" not in caaqms
    )
    assert list(aqi_df.columns) == [
        "station_id",
        "station_name",
        "timestamp",
        "aqi_value",
        "aqi_source",
    ] and aqi_df.aqi_value.tolist() == [100.0, 110.0, 120.0]


# ------------------------------------------------------------------ skip rules, each with its recorded reason
def test_a_healthy_station_is_forecast_and_the_audited_absent_groups_are_reported():
    v = verdict(history(temp_curr=np.nan, solar_rad_curr=np.nan, nox_lag_1h=np.nan))
    assert v.ok and set(v.notes["audited_groups_absent"]) == {"nox", "temp", "solar_rad"}


def test_stale_station_is_skipped_with_its_age():
    v = verdict(latest=ISSUE - pd.Timedelta(hours=9))
    assert not v.ok and v.reason.startswith("stale") and "9.0 h" in v.reason
    assert verdict(latest=ISSUE - pd.Timedelta(hours=3)).ok  # exactly at the limit is still fresh
    assert verdict(latest=None).reason == "no readings in the database"


def test_missing_current_aqi_is_skipped():
    assert verdict(row=False).reason == "current AQI missing at the issue hour"
    frame = history()
    frame.loc[frame.index[-1], "aqi_curr"] = np.nan
    assert verdict(frame).reason == "current AQI missing at the issue hour"


def test_too_little_history_is_skipped_never_imputed():
    v = verdict(history(hours=100))
    assert not v.ok and v.reason.startswith("insufficient history: 100 hourly AQI rows") and "need 169" in v.reason


def test_a_required_group_missing_everywhere_is_skipped():
    v = verdict(history(pm25_lag_1h=np.nan, pm25_lag_24h=np.nan))
    assert not v.ok and "'pm25'" in v.reason
    # a missing audited group is NOT a reason to skip
    assert verdict(history(nox_lag_1h=np.nan)).ok


def test_the_validation_calibrated_gate_skips_degraded_rows():
    frame = history()
    cols = list(fake_models().features["aqi_24h"])
    frame.loc[frame.index[-1], cols[:4]] = np.nan  # 4 of 9 core features = 44%
    v = verdict(frame)
    assert not v.ok and "44.4%" in v.reason and "22.0%" in v.reason
    assert verdict(frame, gate={"max_core_missing_share": 0.5}).ok


def test_run_status_is_failed_partial_or_success():
    ok, bad = forecast.StationVerdict("a", True), forecast.StationVerdict("b", False, "stale")
    assert (
        forecast.classify_run([ok, ok]) == "success"
        and forecast.classify_run([ok, bad]) == "partial"
        and forecast.classify_run([bad]) == "stale"  # every station skipped as stale: nothing fresh, not a fault
        and forecast.classify_run([forecast.StationVerdict("c", False, "insufficient history: 3 rows")]) == "failed"
        and forecast.classify_run([bad, forecast.StationVerdict("c", False, "insufficient history")]) == "failed"
        and forecast.classify_run([]) == "failed"
    )
    assert forecast.summarize([ok, bad])["skipped"] == {"b": "stale"}


# ------------------------------------------------------------------ the job with a fake store
class FakeStore:
    def __init__(self, newest):
        self.newest, self.writes, self.finished = newest, [], []

    def newest_aqi_hour(self):
        return self.newest

    def read_history(self, ids, since, until):
        return pd.DataFrame(), pd.DataFrame()

    def start_run(self, job, run_type="live"):
        return 7

    def finish_run(self, run_id, status, rows, error, details):
        self.finished.append((status, rows, error))

    def register_models(self, specs, hashes, versions):
        self.writes.append("register")
        return 3

    def insert_forecasts(self, rows):
        self.writes.append("insert")
        return len(rows)


def patched_run(monkeypatch, store, verdicts, rows=None, **kw):
    monkeypatch.setattr(forecast, "to_inputs", lambda r, a, w: (pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(
        forecast, "forecast_rows", lambda *a, **k: (rows if rows is not None else pd.DataFrame(), verdicts)
    )
    return forecast.run(store, fake_models(), GATE, {}, now=ISSUE + pd.Timedelta(hours=2), **kw)


ROWS = pd.DataFrame({"station_id": [6], "horizon": [1]})


def test_job_writes_after_registering_models_and_records_skips(monkeypatch):
    store = FakeStore(ISSUE)
    monkeypatch.setattr(forecast, "library_versions", lambda: {})
    result = patched_run(
        monkeypatch,
        store,
        [forecast.StationVerdict("ITO", True), forecast.StationVerdict("Bawana", False, "stale")],
        ROWS,
    )
    assert result["status"] == "partial" and result["rows"] == 1 and store.writes == ["register", "insert"]
    assert store.finished == [("partial", 1, None)] and result["details"]["skipped"] == {"Bawana": "stale"}


def test_dry_run_writes_and_records_nothing(monkeypatch):
    store = FakeStore(ISSUE)
    result = patched_run(monkeypatch, store, [forecast.StationVerdict("ITO", True)], ROWS, dry_run=True)
    assert result["status"] == "success" and result["rows"] == 0 and store.writes == [] and store.finished == []


def test_no_fresh_aqi_fails_the_run_with_a_message(monkeypatch):
    store = FakeStore(ISSUE - pd.Timedelta(hours=30))
    result = patched_run(monkeypatch, store, [])
    assert result["status"] == "stale" and "nothing fresh to forecast from" in result["error"] and store.writes == []
    assert store.finished == [("stale", 0, result["error"])]  # recorded in job_runs, no forecast written
    assert FakeStore(None).newest_aqi_hour() is None
    assert patched_run(monkeypatch, FakeStore(None), [])["error"] == "no AQI rows in the database"


def test_a_replay_with_an_explicit_issue_time_skips_the_freshness_check(monkeypatch):
    result = patched_run(
        monkeypatch,
        FakeStore(ISSUE - pd.Timedelta(days=30)),
        [forecast.StationVerdict("ITO", True)],
        ROWS,
        issue_time=ISSUE - pd.Timedelta(days=30),
        dry_run=True,
    )
    assert result["status"] == "success"


def test_every_station_skipped_fails_and_says_why(monkeypatch):
    result = patched_run(
        monkeypatch,
        FakeStore(ISSUE),
        [forecast.StationVerdict("ITO", False, "stale"), forecast.StationVerdict("Bawana", False, "stale")],
    )
    assert result["status"] == "stale" and "ITO: stale" in result["error"]


def test_a_run_that_skips_everything_for_a_non_stale_reason_still_fails(monkeypatch):
    result = patched_run(
        monkeypatch,
        FakeStore(ISSUE),
        [
            forecast.StationVerdict("ITO", False, "stale"),
            forecast.StationVerdict("Bawana", False, "insufficient history"),
        ],
    )
    assert result["status"] == "failed"


def test_only_a_failed_run_makes_the_workflow_red(monkeypatch):
    class Cfg:
        weather_fill, stale_after_hours = "none", 3.0

    from contextlib import nullcontext

    for status, code in (("success", 0), ("partial", 0), ("stale", 0), ("failed", 1)):
        monkeypatch.setattr("src.live.config.load_config", lambda: Cfg)
        monkeypatch.setattr("src.live.config.load_forecast_config", lambda: {})
        monkeypatch.setattr(forecast.serving, "enabled_specs", lambda cfg: [])
        monkeypatch.setattr(forecast.serving, "verify", lambda specs: {})
        monkeypatch.setattr(forecast.serving, "load", lambda cfg, check=False: None)
        monkeypatch.setattr(forecast, "load_gate", lambda: GATE)
        monkeypatch.setattr("src.live.forecast_store.ForecastStore", lambda var: nullcontext())
        monkeypatch.setattr(
            forecast,
            "run",
            lambda *a, status=status, **k: {
                "status": status,
                "rows": 0,
                "error": None,
                "details": {},
                "forecasts": None,
            },
        )
        assert forecast.main(["--dry-run"]) == code


# ------------------------------------------------------------------ SQL and model artifacts
def test_sql_never_deletes_and_forecasts_are_immutable():
    for text in (
        forecast_store.SELECT_READINGS,
        forecast_store.SELECT_AQI,
        forecast_store.INSERT_FORECASTS,
        forecast_store.UPSERT_MODEL,
    ):
        assert "delete" not in text.lower() and "truncate" not in text.lower()
    assert (
        "do nothing" in forecast_store.INSERT_FORECASTS
        and "(issue_time, station_id, horizon, target)" in forecast_store.INSERT_FORECASTS
    )
    assert "metrics_source = excluded.metrics_source" in forecast_store.UPSERT_MODEL


def test_the_pinned_hashes_match_the_files_in_the_repo():
    assert set(model_mod.verify()) == set(model_mod.artifact_paths())


def test_a_changed_artifact_stops_the_job(tmp_path):
    for rel in model_mod.artifact_paths():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"original " + rel.encode())
    hashes = tmp_path / "hashes.json"
    hashes.write_text(json.dumps(model_mod.compute_hashes(tmp_path)))
    assert model_mod.verify(tmp_path, hashes)
    (tmp_path / model_mod.ARTIFACTS[6]["model"]).write_bytes(b"tampered")
    with pytest.raises(model_mod.ModelHashMismatch, match="lgb_model_6h"):
        model_mod.verify(tmp_path, hashes)
    (tmp_path / model_mod.ARTIFACTS[1]["model"]).unlink()
    with pytest.raises(model_mod.ModelHashMismatch):
        model_mod.verify(tmp_path, hashes)


def test_station_one_hot_names_follow_training():
    rows = pd.DataFrame({"station_name": ["Dwarka-Sector 8", "R K Puram"]})
    out = model_mod.add_station_dummies(rows, ["station_Dwarka-Sector_8", "station_R_K_Puram", "pm25_curr"])
    assert (
        out["station_Dwarka-Sector_8"].tolist() == [1.0, 0.0]
        and out["station_R_K_Puram"].tolist() == [0.0, 1.0]
        and "pm25_curr" not in out
    )


def test_the_gate_file_records_its_validation_derivation():
    gate = forecast.load_gate()
    assert (
        0 < gate["max_core_missing_share"] < 1
        and "validation rows" in gate["derivation"]
        and "2025-09-01" in gate["derivation"]
    )


def test_forecast_workflow_runs_hourly_after_ingest_and_a_manual_run_defaults_to_a_dry_run():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".github/workflows/forecast.yml").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert 'cron: "25 * * * *"' in code and "workflow_dispatch" in code and "default: true" in code
    # only a manual run can be a dry run; the schedule always writes
    assert "github.event_name == 'workflow_dispatch' && inputs.dry_run && '--dry-run'" in code
    assert "contents: read" in code and "python -m src.live.forecast" in code and "requirements-forecast.txt" in code

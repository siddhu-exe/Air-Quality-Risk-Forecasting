"""The products the live job serves: config, hash pinning, prediction kinds, the 1h rule. No database, no network."""

import json

import numpy as np
import pandas as pd
import pytest

from src.features.compute_cpcb_aqi import POLLUTANTS, hourly_aqi_series
from src.live import forecast, forecast_store, serving
from src.live.config import ConfigError, ForecastConfig, load_forecast_config
from src.live.forecast import KST
from src.live.models import ModelHashMismatch

ISSUE = pd.Timestamp("2026-10-07 12:00", tz=KST)


# ------------------------------------------------------------------ config
def test_the_shipped_config_publishes_exactly_the_approved_products():
    config = load_forecast_config()
    assert config.enabled() == ["aqi_1h", "aqi_6h", "aqi_24h", "pm25_1h", "pm25_6h"]
    assert (config.aqi_1h, config.pm25_24h, config.interval_24h, config.p_severe) == ("rule", "off", "off", "off")


@pytest.mark.parametrize(
    "setting, message",
    [
        ({"pm25_24h": "model"}, "no 24h PM2.5"),
        ({"interval_24h": "model"}, "80%"),
        ({"p_severe": "model"}, "Brier"),
        ({"aqi_1h": "model"}, "must be one of"),  # the retrained 1h LightGBM cannot be selected: it loses to the rule
        ({"aqi_6h": "rule"}, "must be one of"),
    ],
)
def test_refused_products_cannot_be_switched_on(setting, message):
    with pytest.raises(ConfigError, match=message):
        ForecastConfig(**setting)


def test_unknown_forecast_settings_are_rejected(tmp_path):
    path = tmp_path / "live.toml"
    path.write_text('[forecast]\naqi_2h = "rule"\n')
    with pytest.raises(ConfigError, match="unknown"):
        load_forecast_config(path)
    assert ForecastConfig(aqi_6h="off").enabled() == ["aqi_1h", "aqi_24h", "pm25_1h", "pm25_6h"]


# ------------------------------------------------------------------ registry and hashes
def test_there_is_no_24h_pm25_product_and_the_1h_product_is_the_rule():
    assert {(s.target, s.horizon) for s in serving.SPECS.values()} == {
        ("aqi", 1),
        ("aqi", 6),
        ("aqi", 24),
        ("pm25", 1),
        ("pm25", 6),
    }
    assert serving.SPECS["aqi_1h"].kind == "rule" and not serving.SPECS["aqi_1h"].files
    assert "rule-based (24h-window update)" in serving.SPECS["aqi_1h"].name.lower()


def test_the_pinned_hashes_match_the_files_in_the_repo():
    hashes = serving.verify()
    assert set(serving.artifact_paths()) <= set(hashes)
    assert serving.RULES_FILE in hashes  # the rule's source is recorded in the registry


def test_every_served_file_is_pinned_and_the_disabled_models_are_pinned_too():
    pinned = set(json.loads(serving.HASHES_PATH.read_text()))
    assert set(serving.artifact_paths()) <= pinned
    assert "models/live/aqi-1h-lgb-live-v1.joblib" in pinned  # kept, disabled in config
    assert "models/live/pm25/pm25-24h-hgb-live-v1.joblib" in pinned


def test_a_changed_or_unpinned_artifact_stops_the_job(tmp_path):
    specs = [serving.SPECS["aqi_6h"], serving.SPECS["pm25_1h"]]
    for rel in serving.artifact_paths(specs):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"original " + rel.encode())
    (tmp_path / serving.RULES_FILE).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / serving.RULES_FILE).write_text("# rule")
    pins = tmp_path / "pins.json"
    from src.live.models import sha256_of

    pins.write_text(json.dumps({rel: sha256_of(tmp_path / rel) for rel in serving.artifact_paths(specs)}))
    assert serving.verify(specs, tmp_path, pins)
    target = tmp_path / serving.SPECS["aqi_6h"].files["model"]
    target.write_bytes(b"tampered")
    with pytest.raises(ModelHashMismatch, match="aqi-6h-lgb-live-v1"):
        serving.verify(specs, tmp_path, pins)
    pins.write_text("{}")
    with pytest.raises(ModelHashMismatch):
        serving.verify(specs, tmp_path, pins)  # a model whose hash is not pinned is not served


# ------------------------------------------------------------------ prediction kinds, with stand-in models
class Constant:
    def __init__(self, value, names=()):
        self.value, self.names = value, list(names)

    def predict(self, frame):
        return np.full(len(frame), self.value, dtype=float)

    def feature_name(self):
        return self.names

    def transform(self, frame):
        return np.asarray(frame, dtype=float)


def rows(n=2):
    return pd.DataFrame(
        {
            "station_id": [6, 3][:n],
            "station_name": ["ITO", "Alipur"][:n],
            "aqi_curr": [100.0, 200.0][:n],
            "pm25_curr": [40.0, 80.0][:n],
            "f": 1.0,
        }
    )


def served(key, loaded, names):
    return serving.Serving([serving.SPECS[key]], {key: loaded}, {key: names})


def test_lgb_scores_the_booster_on_its_own_feature_list():
    models = served("aqi_6h", Constant(150.0, ["f"]), ["f"])
    assert serving.predict(models, "aqi_6h", rows()).tolist() == [150.0, 150.0]


def test_hybrid_is_half_persistence_half_ridge():
    parts = {"model": Constant(300.0), "imputer": Constant(0), "scaler": Constant(0)}
    models = served("aqi_24h", parts, ["f"])
    assert serving.predict(models, "aqi_24h", rows()).tolist() == [0.5 * 100 + 150, 0.5 * 200 + 150]


@pytest.mark.parametrize("form, expected", [("level", [30.0, 30.0]), ("residual", [70.0, 110.0])])
def test_pm25_models_add_the_current_value_only_in_residual_form(form, expected):
    models = served("pm25_1h", {"model": Constant(30.0), "columns": ["f"], "target_form": form}, ["f"])
    assert serving.predict(models, "pm25_1h", rows()).tolist() == expected


def test_the_rule_is_not_a_fitted_model():
    with pytest.raises(ValueError, match="not a fitted model"):
        serving.predict(served("aqi_1h", None, []), "aqi_1h", rows())


def test_persistence_is_the_current_value_of_the_target():
    assert serving.persistence(serving.SPECS["aqi_6h"], rows()).tolist() == [100.0, 200.0]
    assert serving.persistence(serving.SPECS["pm25_6h"], rows()).tolist() == [40.0, 80.0]


# ------------------------------------------------------------------ the 1h rule on stored readings
def readings(hours=60, **override):
    stamps = pd.date_range(end=ISSUE, periods=hours, freq="h")
    frame = pd.DataFrame(
        {
            "timestamp": stamps,
            "station_name": "ITO",
            **{p: v for p, v in zip(POLLUTANTS, [90, 150, 40, 10, 20, 1.0, 30])},
        }
    )
    for column, value in override.items():
        frame[column] = value
    return frame


def stored_aqi(frame):
    series = frame.set_index("timestamp")[POLLUTANTS]
    return hourly_aqi_series(series).rolling(24, min_periods=16).mean().iloc[-1]


def test_rule_on_flat_air_equals_the_current_aqi():
    frame = readings()
    value, why = forecast.rule_value(frame, "ITO", ISSUE, stored_aqi(frame))
    assert why == "" and value == pytest.approx(stored_aqi(frame))


def test_rule_follows_the_hour_leaving_the_window():
    frame = readings()
    frame.loc[frame.index[-24], "pm25"] = 250.0  # a dirty hour about to leave the 24h window
    aqi = stored_aqi(frame)
    value, _ = forecast.rule_value(frame, "ITO", ISSUE, aqi)
    assert value < aqi  # the 24h mean falls once that hour is replaced by the current (cleaner) hour


def test_rule_is_withheld_without_a_current_hour_or_with_a_mismatching_stored_aqi():
    frame = readings()
    gappy = frame.iloc[:-1]
    value, why = forecast.rule_value(gappy, "ITO", ISSUE, 100.0)
    assert value is None and "no valid current hourly AQI" in why
    value, why = forecast.rule_value(frame, "ITO", ISSUE, stored_aqi(frame) + 5)
    assert value is None and "stored AQI" in why
    sparse = readings(hours=60)
    sparse.loc[sparse.index[-30:-2], POLLUTANTS] = np.nan
    assert forecast.rule_value(sparse, "ITO", ISSUE, 100.0)[0] is None


def test_assemble_writes_each_product_with_its_target_and_the_rule_only_where_it_passed():
    models = serving.Serving(
        [serving.SPECS["aqi_1h"], serving.SPECS["aqi_6h"], serving.SPECS["pm25_6h"]],
        {
            "aqi_6h": Constant(150.0, ["f"]),
            "pm25_6h": {"model": Constant(30.0), "columns": ["f"], "target_form": "level"},
        },
        {"aqi_6h": ["f"], "pm25_6h": ["f"]},
    )
    out, dropped = forecast.assemble(
        rows(), ISSUE, models, {"ITO": forecast.WindowUpdate({1: 101.5, 6: 90.0, 24: 80.0}, "")}
    )
    key = out.set_index(["target", "horizon", "station_name"])
    assert len(out) == 1 + 2 + 2 and set(out.model_version) == {
        "aqi-1h-window-update-v1",
        "aqi-6h-lgb-live-v1",
        "pm25-6h-hgb-live-v1",
    }
    assert key.loc[("aqi", 1, "ITO"), "y_hat"] == 101.5 and ("aqi", 1, "Alipur") not in key.index
    assert dropped == [{"station": "Alipur", "product": "aqi_1h", "reason": "no window-update value"}]
    # the reference is frozen per row: window-update where known, persistence where not, nothing for PM2.5
    assert key.loc[("aqi", 6, "ITO"), "y_window_update"] == 90.0
    assert key.loc[("aqi", 6, "Alipur"), "y_window_update"] == 200.0
    assert np.isnan(key.loc[("pm25", 6, "ITO"), "y_window_update"]) and (out.run_type == "live").all()
    assert key.loc[("pm25", 6, "Alipur"), "y_persistence"] == 80.0
    assert (out.target_time - out.issue_time == pd.to_timedelta(out.horizon, unit="h")).all()


# ------------------------------------------------------------------ the real files: loadable only in the training environment
def _real_models_loadable() -> str | None:
    try:
        import lightgbm  # noqa: F401
    except ModuleNotFoundError:
        return "lightgbm is not installed"
    if int(np.__version__.split(".")[0]) < 2:
        return "the PM2.5 models were pickled under numpy 2 (requirements-forecast.txt)"
    return None


@pytest.mark.skipif(_real_models_loadable() is not None, reason=str(_real_models_loadable()))
def test_the_real_models_load_and_forecast_finite_values_from_a_sparse_row():
    models = serving.load(load_forecast_config())
    frame = rows(1)
    for key in ("aqi_6h", "aqi_24h", "pm25_1h", "pm25_6h"):
        for name in models.features[key]:
            if name not in frame and not name.startswith("station_"):
                frame[name] = np.nan
        out = serving.predict(models, key, frame)
        assert out.shape == (1,) and np.isfinite(out).all(), key


def test_a_product_without_a_finite_value_is_dropped_for_that_station_only():
    models = serving.Serving(
        [serving.SPECS["pm25_6h"], serving.SPECS["aqi_6h"]],
        {
            "aqi_6h": Constant(150.0, ["f"]),
            "pm25_6h": {"model": Constant(30.0), "columns": ["f"], "target_form": "residual"},
        },
        {"aqi_6h": ["f"], "pm25_6h": ["f"]},
    )
    frame = rows()
    frame.loc[1, "pm25_curr"] = np.nan  # Alipur has no current PM2.5
    out, dropped = forecast.assemble(frame, ISSUE, models)
    assert out.groupby("target").station_name.apply(list).to_dict() == {"aqi": ["ITO", "Alipur"], "pm25": ["ITO"]}
    assert dropped == [{"station": "Alipur", "product": "pm25_6h", "reason": "no current pm25 value at the issue hour"}]
    assert np.isfinite(out[["y_hat", "y_persistence"]].to_numpy(float)).all()


def test_dropped_products_are_recorded_and_make_the_run_partial():
    ok = forecast.StationVerdict(
        "ITO", True, None, {"products_dropped": {"pm25_1h": "no current pm25 value at the issue hour"}}
    )
    clean = forecast.StationVerdict("Bawana", True)
    assert forecast.classify_run([clean, clean]) == "success"
    assert forecast.classify_run([clean, ok]) == "partial"
    assert forecast.summarize([clean, ok])["skipped_products"] == {
        "ITO/pm25_1h": "no current pm25 value at the issue hour"
    }


def test_window_update_references_cover_every_aqi_horizon_and_agree_with_the_rule():
    frame = readings()
    aqi = stored_aqi(frame)
    reference = forecast.window_update_references(frame, "ITO", ISSUE, aqi)
    assert set(reference.values) == {1, 6, 24} and reference.reason == ""
    assert reference.values[1] == forecast.rule_value(frame, "ITO", ISSUE, aqi)[0]
    assert all(
        v == pytest.approx(aqi) for v in reference.values.values()
    )  # flat air: every horizon equals the current AQI
    bad = forecast.window_update_references(frame, "ITO", ISSUE, aqi + 9)
    assert bad.values == {} and "stored AQI" in bad.reason


def test_the_insert_carries_the_frozen_references_and_the_run_type():
    sql = forecast_store.INSERT_FORECASTS
    assert "y_window_update" in sql and "run_type" in sql

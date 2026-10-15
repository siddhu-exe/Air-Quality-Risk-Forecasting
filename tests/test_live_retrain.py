"""Light checks for the live-consistent retrain pieces (no LightGBM, no data files)."""
import json

import numpy as np
import pandas as pd
import pytest

from src.features.build_live_matrix import MASKED_AT, MASKED_EVERYWHERE, apply_mask
from src.models import live_overrides, live_retrain


def _caaqms():
    n = 4
    frame = pd.DataFrame({"station_name": ["ITO", "ITO", "Bawana", "Bawana"], "pm25": [1.0] * n})
    for column in [*MASKED_EVERYWHERE, *MASKED_AT["ITO"], "no2"]:
        frame[column] = 5.0
    return frame


def test_live_mask_blanks_only_the_inputs_the_live_sources_lack():
    out = apply_mask(_caaqms(), "live")
    assert out[MASKED_EVERYWHERE].isna().all().all()
    assert out.loc[out.station_name == "ITO", MASKED_AT["ITO"]].isna().all().all()
    assert out.loc[out.station_name == "Bawana", MASKED_AT["ITO"]].notna().all().all()   # other stations keep weather
    assert out[["pm25", "no2"]].notna().all().all()
    assert apply_mask(_caaqms(), "none").notna().all().all()
    with pytest.raises(ValueError):
        apply_mask(_caaqms(), "bogus")


def test_station_dummies_use_the_training_column_names():
    frame = pd.DataFrame({"station_name": ["Dwarka-Sector 8", "R K Puram"]})
    out = live_retrain.add_station_dummies(frame)
    assert out["station_Dwarka-Sector_8"].tolist() == [1.0, 0.0] and out["station_R_K_Puram"].tolist() == [0.0, 1.0]


def test_hybrid_blends_half_persistence_half_ridge():
    rng = np.random.default_rng(0)
    train = pd.DataFrame({"a": rng.normal(size=200), "aqi_curr": 100 + rng.normal(size=200)})
    train["y"] = 3 * train["a"] + 100
    parts = live_retrain.fit_hybrid(train, ["a"], "y")
    pred = live_retrain.predict_hybrid(parts, train, ["a"])
    ridge_only = parts["ridge"].predict(parts["scaler"].transform(parts["imputer"].transform(train[["a"]])))
    assert np.allclose(pred, 0.5 * train["aqi_curr"] + 0.5 * ridge_only)


def test_prune_columns_is_a_noop_without_the_live_env_and_drops_empty_columns_with_it(monkeypatch):
    frame = pd.DataFrame({"ok": [1.0, 2.0, 3.0], "empty": [np.nan] * 3, "const": [4.0] * 3})
    monkeypatch.delenv("LIVE_MATRIX_PATH", raising=False)
    assert live_overrides.prune_columns(frame, list(frame)) == ["ok", "empty", "const"]
    monkeypatch.setenv("LIVE_MATRIX_PATH", "x.parquet")
    assert live_overrides.prune_columns(frame, list(frame)) == ["ok"]


def test_export_writes_manifest_only_when_asked(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_EXPORT_DIR", raising=False)
    assert live_overrides.export("m", {"x": 1}, {}) is None
    monkeypatch.setenv("LIVE_EXPORT_DIR", str(tmp_path))
    path = live_overrides.export("m", {"x": 1}, {"horizon_hours": 6})
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert path.exists() and manifest["m"]["horizon_hours"] == 6 and len(manifest["m"]["sha256"]) == 64


def test_retrain_refuses_a_second_test_scoring(tmp_path, monkeypatch):
    monkeypatch.setattr(live_retrain, "OUT_DIR", tmp_path)
    (tmp_path / "test_scored.json").write_text("{}")
    monkeypatch.delenv("LIVE_RETRAIN_ALLOW_RESCORE", raising=False)
    with pytest.raises(SystemExit, match="scored once"):
        live_retrain.main([1])

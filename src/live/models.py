"""The frozen AQI models as the forecast job uses them: hash-verified artifacts, one predict function per family.

Nothing here trains or modifies a model. ``config/model_hashes.json`` pins the sha256 of every artifact; a mismatch
stops the job (an edited or replaced file must never silently produce live forecasts).

  1h / 6h  LightGBM Booster fed the raw feature row (NaN handled natively), 131 features incl. station one-hots
  24h      0.5 x persistence + 0.5 x Ridge(imputer -> scaler -> ridge) on the 49 refined features
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
HASHES_PATH = REPO_ROOT / "config" / "model_hashes.json"

FOLDER_24H = Path("models/24h/final")
ARTIFACTS = {
    1: {"model": "models/lgb_model_1h_v1.joblib"},
    6: {"model": "models/lgb_model_6h_v1.joblib"},
    24: {
        "model": str(FOLDER_24H / "24h_final_model.joblib"),
        "imputer": str(FOLDER_24H / "imputer_final_24h.joblib"),
        "scaler": str(FOLDER_24H / "scaler_final_24h.joblib"),
        "features": str(FOLDER_24H / "feature_names_final.joblib"),
    },
}
#: model_version written to aq.model_registry / aq.forecasts
VERSIONS = {1: "aqi-1h-lgb-v1", 6: "aqi-6h-lgb-v1", 24: "aqi-24h-hybrid-v1"}
NAMES = {1: "LightGBM 1h AQI", 6: "LightGBM 6h AQI", 24: "50/50 persistence + Ridge 24h AQI"}
TRAINING_WINDOW = (
    "train Jan-Aug 2025; validation Sep-Oct 2025; test Nov-Dec 2025 (reports/modeling/PHASE_6_FINAL_AUDIT.md)"
)
METRICS_SOURCE = "reports/metrics/headline_metrics.csv"
BLEND_WEIGHT_PERSISTENCE = 0.5


class ModelHashMismatch(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_paths() -> list[str]:
    return [p for files in ARTIFACTS.values() for p in files.values()]


def compute_hashes(root: Path = REPO_ROOT) -> dict[str, str]:
    return {p: sha256_of(root / p) for p in artifact_paths()}


def verify(root: Path = REPO_ROOT, hashes_path: Path = HASHES_PATH) -> dict[str, str]:
    """Re-hash every artifact against ``config/model_hashes.json``. Returns the hashes; raises ModelHashMismatch."""
    expected = json.loads(hashes_path.read_text())
    actual, bad = {}, []
    for rel in artifact_paths():
        path = root / rel
        actual[rel] = sha256_of(path) if path.exists() else "MISSING"
        if actual[rel] != expected.get(rel):
            bad.append(rel)
    if bad:
        raise ModelHashMismatch(f"model artifact(s) differ from config/model_hashes.json: {bad}")
    return actual


@dataclass
class Models:
    boosters: dict  # {1: Booster, 6: Booster}
    ridge: object
    imputer: object
    scaler: object
    features_24h: list
    features: dict  # {horizon: [feature names the model expects]}


def load(root: Path = REPO_ROOT, check: bool = True, horizons: tuple = (1, 6, 24)) -> Models:
    """Load the models for ``horizons`` (LightGBM is only needed, and only imported, when 1h or 6h is requested)."""
    if check:
        verify(root)
    boosters = {}
    try:
        for horizon in [h for h in (1, 6) if h in horizons]:
            boosters[horizon] = joblib.load(root / ARTIFACTS[horizon]["model"])
    except ModuleNotFoundError as exc:  # joblib unpickles lightgbm.basic.Booster
        raise RuntimeError(
            "lightgbm is required for the 1h/6h models (pip install -r requirements-forecast.txt)"
        ) from exc
    files = ARTIFACTS[24]
    features_24h = list(joblib.load(root / files["features"]))
    return Models(
        boosters=boosters,
        ridge=joblib.load(root / files["model"]),
        imputer=joblib.load(root / files["imputer"]),
        scaler=joblib.load(root / files["scaler"]),
        features_24h=features_24h,
        features={**{h: list(b.feature_name()) for h, b in boosters.items()}, 24: features_24h},
    )


def station_dummy_name(station_name: str) -> str:
    """Training used ``pd.get_dummies(df.station_name, prefix='station')``: spaces become underscores in the column name."""
    return "station_" + station_name.replace(" ", "_")


def add_station_dummies(rows: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    out = rows.copy()
    for name in feature_names:
        if name.startswith("station_") and name not in out:
            out[name] = (out["station_name"].map(station_dummy_name) == name).astype(float)
    return out


def predict_lgb(models: Models, horizon: int, rows: pd.DataFrame) -> np.ndarray:
    names = models.features[horizon]
    return models.boosters[horizon].predict(add_station_dummies(rows, names)[names])


def predict_24h(models: Models, rows: pd.DataFrame) -> np.ndarray:
    """0.5 x persistence + 0.5 x Ridge. ``rows`` must already hold the multi-day features (see forecast.add_long_horizon)."""
    ridge_part = models.ridge.predict(models.scaler.transform(models.imputer.transform(rows[models.features_24h])))
    return BLEND_WEIGHT_PERSISTENCE * rows["aqi_curr"].to_numpy(float) + (1 - BLEND_WEIGHT_PERSISTENCE) * ridge_part


def predict(models: Models, horizon: int, rows: pd.DataFrame) -> np.ndarray:
    return predict_24h(models, rows) if horizon == 24 else predict_lgb(models, horizon, rows)

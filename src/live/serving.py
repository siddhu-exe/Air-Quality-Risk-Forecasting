"""The forecast products the live job serves: live-consistent models (trained on recomputed AQI) and one rule.

``config/live_model_hashes.json`` pins the sha256 of every file under ``models/live/``; a mismatch stops the job. Which
products run is ``[forecast]`` in ``config/live.toml``. The frozen research models are not served; they stay behind
``src/live/models.py`` for parity checks and the retrain's reference rows (ADR 0001).

  aqi 1h    rule: window-update persistence (``src/live/rules.py``), no file, no model
  aqi 6h    LightGBM Booster on the raw feature row (131 features incl. station one-hots)
  aqi 24h   0.5 x persistence + 0.5 x Ridge(imputer -> scaler -> ridge) on the 49 refined features
  pm25 1h/6h  HistGradientBoosting, level or residual (+ current PM2.5) as selected on validation

Nothing here trains or modifies a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.live import rules
from src.live.config import ForecastConfig
from src.live.models import BLEND_WEIGHT_PERSISTENCE, ModelHashMismatch, add_station_dummies, sha256_of

REPO_ROOT = Path(__file__).resolve().parents[2]
HASHES_PATH = REPO_ROOT / "config" / "live_model_hashes.json"
LIVE_DIR = Path("models/live")
HYBRID_24H = LIVE_DIR / "aqi-24h-hybrid-live-v1"
RETRAIN_METRICS = "reports/modeling/live_retrain/live_retrain_metrics.csv"
PM25_METRICS = "reports/modeling/live_pm25/pm25_forecast_metrics.csv"
WINDOW_UPDATE_METRICS = "reports/modeling/live_retrain/window_update_baseline.csv"
RULES_FILE = "src/live/rules.py"
TRAINING_WINDOW = "train 2024-01..2025-08 (24h embargo); validation Sep-Oct 2025; test Nov-Dec 2025 (recomputed AQI)"


@dataclass(frozen=True)
class Spec:
    """One published forecast product."""

    key: str  # the [forecast] config key
    target: str  # "aqi" | "pm25"
    horizon: int
    kind: str  # "rule" | "lgb" | "hybrid" | "hgb"
    version: str  # model_version written to aq.model_registry / aq.forecasts
    name: str
    files: dict[str, str] = field(default_factory=dict)  # role -> repo-relative path (empty for the rule)
    metrics_source: str = ""

    @property
    def primary_file(self) -> str:
        """The file the registry row points at and hashes: the model, or the module holding the rule."""
        return self.files.get("model") or RULES_FILE


SPECS: dict[str, Spec] = {
    s.key: s
    for s in (
        Spec(
            "aqi_1h",
            "aqi",
            1,
            "rule",
            rules.AQI_1H_VERSION,
            rules.AQI_1H_NAME,
            metrics_source=WINDOW_UPDATE_METRICS,
        ),
        Spec(
            "aqi_6h",
            "aqi",
            6,
            "lgb",
            "aqi-6h-lgb-live-v1",
            "LightGBM 6h AQI (live-consistent)",
            {"model": str(LIVE_DIR / "aqi-6h-lgb-live-v1.joblib")},
            RETRAIN_METRICS,
        ),
        Spec(
            "aqi_24h",
            "aqi",
            24,
            "hybrid",
            "aqi-24h-hybrid-live-v1",
            "50/50 persistence + Ridge 24h AQI (live-consistent, low skill)",
            {
                "model": str(HYBRID_24H / "model.joblib"),
                "imputer": str(HYBRID_24H / "imputer.joblib"),
                "scaler": str(HYBRID_24H / "scaler.joblib"),
                "features": str(HYBRID_24H / "features.joblib"),
            },
            RETRAIN_METRICS,
        ),
        Spec(
            "pm25_1h",
            "pm25",
            1,
            "hgb",
            "pm25-1h-hgb-live-v1",
            "HistGradientBoosting 1h PM2.5 (live-consistent)",
            {"model": str(LIVE_DIR / "pm25" / "pm25-1h-hgb-live-v1.joblib")},
            PM25_METRICS,
        ),
        Spec(
            "pm25_6h",
            "pm25",
            6,
            "hgb",
            "pm25-6h-hgb-live-v1",
            "HistGradientBoosting 6h PM2.5 (live-consistent)",
            {"model": str(LIVE_DIR / "pm25" / "pm25-6h-hgb-live-v1.joblib")},
            PM25_METRICS,
        ),
    )
}


def enabled_specs(config: ForecastConfig) -> list[Spec]:
    return [SPECS[key] for key in config.enabled()]


def artifact_paths(specs: list[Spec] | None = None) -> list[str]:
    return sorted({p for spec in (specs or SPECS.values()) for p in spec.files.values()})


def verify(specs: list[Spec] | None = None, root: Path = REPO_ROOT, hashes_path: Path = HASHES_PATH) -> dict[str, str]:
    """Re-hash every artifact of ``specs`` against ``config/live_model_hashes.json``; raises ModelHashMismatch.

    A file the registry does not list counts as a mismatch, so a new model cannot be served before its hash is pinned."""
    expected = json.loads(hashes_path.read_text())
    actual, bad = {}, []
    for rel in artifact_paths(specs):
        path = root / rel
        actual[rel] = sha256_of(path) if path.exists() else "MISSING"
        if actual[rel] != expected.get(rel):
            bad.append(rel)
    if bad:
        raise ModelHashMismatch(f"model artifact(s) differ from config/live_model_hashes.json: {bad}")
    if any(spec.kind == "rule" for spec in specs or SPECS.values()):
        actual[RULES_FILE] = sha256_of(root / RULES_FILE)  # recorded in the registry, not pinned: it is source code
    return actual


@dataclass
class Serving:
    """Loaded products. ``features`` maps product key -> the feature names its model reads (empty for the rule)."""

    specs: list[Spec]
    loaded: dict[str, Any]
    features: dict[str, list[str]]

    def spec(self, key: str) -> Spec:
        return next(s for s in self.specs if s.key == key)

    def has(self, key: str) -> bool:
        return any(s.key == key for s in self.specs)


def load(config: ForecastConfig, root: Path = REPO_ROOT, check: bool = True) -> Serving:
    specs = enabled_specs(config)
    if check:
        verify(specs, root)
    loaded: dict[str, Any] = {}
    features: dict[str, list[str]] = {}
    try:
        for spec in specs:
            if spec.kind == "rule":
                continue
            if spec.kind == "hybrid":
                parts = {role: joblib.load(root / rel) for role, rel in spec.files.items()}
                loaded[spec.key] = parts
                features[spec.key] = list(parts["features"])
            elif spec.kind == "lgb":
                loaded[spec.key] = joblib.load(root / spec.files["model"])
                features[spec.key] = list(loaded[spec.key].feature_name())
            else:
                payload = joblib.load(root / spec.files["model"])
                loaded[spec.key] = payload
                features[spec.key] = list(payload["columns"])
    except ModuleNotFoundError as exc:  # joblib unpickles lightgbm.basic.Booster
        raise RuntimeError("lightgbm is required (pip install -r requirements-forecast.txt)") from exc
    return Serving(specs, loaded, features)


def predict(serving: Serving, key: str, rows: pd.DataFrame) -> np.ndarray:
    """Model forecast for ``key`` on feature ``rows`` (one per station, all at the issue hour). Not for the rule."""
    spec = serving.spec(key)
    names = serving.features[key]
    if spec.kind == "lgb":
        return serving.loaded[key].predict(add_station_dummies(rows, names)[names])
    if spec.kind == "hybrid":
        parts = serving.loaded[key]
        ridge = parts["model"].predict(parts["scaler"].transform(parts["imputer"].transform(rows[names])))
        return BLEND_WEIGHT_PERSISTENCE * rows["aqi_curr"].to_numpy(float) + (1 - BLEND_WEIGHT_PERSISTENCE) * ridge
    if spec.kind == "hgb":
        payload = serving.loaded[key]
        raw = payload["model"].predict(add_station_dummies(rows, names)[names])
        return raw + rows["pm25_curr"].to_numpy(float) if payload["target_form"] == "residual" else raw
    raise ValueError(f"{key} is a {spec.kind}, not a fitted model")


def persistence(spec: Spec, rows: pd.DataFrame) -> np.ndarray:
    """The plain-persistence reference written beside every forecast: the current value of the forecast target."""
    return rows["aqi_curr" if spec.target == "aqi" else "pm25_curr"].to_numpy(float)

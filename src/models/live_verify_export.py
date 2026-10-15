"""Fail-loudly check of the exported live models: re-hash every file against its manifest, reload it, predict a few validation rows.

    python -m src.models.live_verify_export [--models-dir models/live]

Reads manifests written by ``live_retrain`` (models/live/manifest.json) and ``live_overrides.export`` (models/live/pm25/,
models/live/quantile/). Exits non-zero on any mismatch, missing file, or non-finite prediction. Never modifies anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np

from src.models.live_retrain import FEATURES_PATH, MASKED_PATH, load_matrix

REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(models_dir: Path) -> list[str]:
    problems: list[str] = []
    plain, masked = load_matrix(FEATURES_PATH, True), load_matrix(MASKED_PATH, True)
    val_plain, val_masked = plain[plain.split == "val"].head(200), masked[masked.split == "val"].head(200)

    manifest = json.loads((models_dir / "manifest.json").read_text())
    for version, entry in manifest["models"].items():
        for rel, expected in entry["files"].items():
            path = models_dir / rel
            if not path.exists() or sha256(path) != expected:
                problems.append(f"{version}: {rel} missing or hash differs from manifest")
        horizon, features = entry["horizon_hours"], entry["features"]
        if horizon in (1, 6):
            booster = joblib.load(models_dir / f"{version}.joblib")
            pred = booster.predict(val_plain[features])
            if booster.num_trees() != entry["best_iteration"]:
                problems.append(f"{version}: {booster.num_trees()} trees, manifest says best_iteration {entry['best_iteration']}")
        else:
            folder = models_dir / version
            parts = {n: joblib.load(folder / f"{n}.joblib") for n in ("model", "imputer", "scaler")}
            pred = 0.5 * val_plain["aqi_curr"].to_numpy(float) + 0.5 * parts["model"].predict(parts["scaler"].transform(parts["imputer"].transform(val_plain[features])))
        if not np.isfinite(pred).all() or len(pred) == 0:
            problems.append(f"{version}: non-finite or empty predictions")
        print(f"ok {version}: {len(entry['files'])} files re-hashed, {len(pred)} validation rows predicted")

    for sub in ("pm25", "quantile"):
        manifest_path = models_dir / sub / "manifest.json"
        if not manifest_path.exists():
            problems.append(f"{sub}: manifest.json missing")
            continue
        for name, entry in json.loads(manifest_path.read_text()).items():
            path = models_dir / sub / entry["file"]
            if not path.exists() or sha256(path) != entry["sha256"]:
                problems.append(f"{name}: file missing or hash differs from manifest")
                continue
            payload = joblib.load(path)
            columns = payload["columns"]
            if "model" in payload:
                pred = payload["model"].predict(val_masked[columns])
            else:
                pred = np.vstack([m.predict(val_masked[columns]) for m in payload["quantile_models"].values()] + [payload["classifier"].predict_proba(val_masked[columns])[:, 1]])
            if not np.isfinite(pred).all():
                problems.append(f"{name}: non-finite predictions")
            print(f"ok {name}: hash matches, {len(columns)} columns, predictions finite")
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models-dir", type=Path, default=REPO_ROOT / "models" / "live")
    problems = check(parser.parse_args().models_dir)
    for line in problems:
        print("FAIL", line)
    sys.exit(1 if problems else 0)

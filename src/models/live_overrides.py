"""Opt-in overrides that let the Tier 2 PM2.5 / quantile scripts run on the live-consistent matrix and export their models.

Nothing changes unless the environment variables are set, so the accepted Tier 2 results and their output folders are untouched:

  LIVE_MATRIX_PATH  feature matrix to read instead of data/processed/features_extended.parquet
  LIVE_OUT_DIR      where reports go instead of reports/modeling/<task>/
  LIVE_EXPORT_DIR   when set, the selected models are written there (``export``) with a manifest entry (sha256 of the file)

Exports are only supported for the ``standard`` profile, where the iteration count is fixed (no staged selection to replay).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import joblib


def matrix_path(default: Path) -> Path:
    return Path(os.environ.get("LIVE_MATRIX_PATH") or default)


def prune_columns(train, columns: list[str]) -> list[str]:
    """Live matrices only: drop columns with fewer than 2 distinct non-null values in the training rows.

    The live-masked matrix blanks NOx/NO/solar (and ITO weather), so their derived columns are all-NaN; scikit-learn's
    HistGradientBoosting cannot bin a column with no values. A no-op when LIVE_MATRIX_PATH is not set (Tier 2 behaviour).
    """
    if not os.environ.get("LIVE_MATRIX_PATH"):
        return columns
    kept = [c for c in columns if train[c].nunique(dropna=True) >= 2]
    dropped = len(columns) - len(kept)
    if dropped:
        print(f"live matrix: dropped {dropped} columns with fewer than 2 distinct training values", flush=True)
    return kept


def report_dir(default: Path) -> Path:
    return Path(os.environ["LIVE_OUT_DIR"]) if os.environ.get("LIVE_OUT_DIR") else default


def export_dir() -> Path | None:
    return Path(os.environ["LIVE_EXPORT_DIR"]) if os.environ.get("LIVE_EXPORT_DIR") else None


def export(name: str, payload: dict, meta: dict) -> Path | None:
    """Write ``payload`` as ``<name>.joblib`` and record it in ``manifest.json`` next to it. No-op without LIVE_EXPORT_DIR."""
    folder = export_dir()
    if folder is None:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.joblib"
    joblib.dump(payload, path)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest[name] = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **meta}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return path

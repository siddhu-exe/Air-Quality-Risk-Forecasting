"""
retrain_24h_extended.py
========================
Retrains the frozen 24h 50/50 hybrid (persistence + Ridge alpha=1000 on the
curated feature set) on the extended window that now includes a prior winter.

Difference vs the frozen Phase 6C model is only the training data:
  * frozen : train = 2025-01-01 .. 2025-08-31 (no winter peak)
  * extended: train = 2024-01-01 .. 2025-08-31 (Jan/Feb 2024 + Dec 2024 winters,
              using the CPCB-recomputed AQI for 2024)

Validation (2025-09-01..10-31) and test (2025-11-01..12-31) are unchanged so the
result is directly comparable to the frozen model. Training rows issued in the last
24h before the validation window are dropped (their t+24 label falls inside it). Model family, feature set and
hyper-parameters are held fixed to isolate the effect of the extra winters.

Outputs
-------
  reports/modeling/24h/final/final_predictions_extended.parquet
  reports/modeling/24h/final/val_predictions_extended.parquet
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src.models.phase_6c_refinement import (
    construct_causal_long_horizon_features,
    define_feature_candidate_sets,
    evaluate_metrics,
)
from src.models.splits import assign_split, training_rows

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_extended.parquet"
FEATURE_NAMES_AB = REPO_ROOT / "models" / "24h" / "feature_names_ab.joblib"
OUT_DIR = REPO_ROOT / "reports" / "modeling" / "24h" / "final"
KST = "Asia/Kolkata"

ALPHA = 1000.0
BLEND_NAIVE = 0.50


def main() -> None:
    print("Loading extended feature matrix...")
    frame = pd.read_parquet(FEATURES_PATH)
    frame = construct_causal_long_horizon_features(frame)
    frame["split"] = assign_split(frame["timestamp"])
    frame = frame.dropna(subset=["target_aqi_24h"])
    print("Split sizes:", frame["split"].value_counts().to_dict())

    feature_names_ab = joblib.load(FEATURE_NAMES_AB)
    candidate_sets = define_feature_candidate_sets(feature_names_ab)
    refined_cols = [c for c in candidate_sets["Set Refined (Curated 54 Feats)"] if c in frame.columns]
    print(f"Refined feature set: {len(refined_cols)} features")

    train = training_rows(frame)  # 24h embargo: no train label reaches the val window
    val = frame[frame["split"] == "val"]
    test = frame[frame["split"] == "test"]

    imp = SimpleImputer(strategy="median")
    scl = StandardScaler()
    x_train = scl.fit_transform(imp.fit_transform(train[refined_cols]))
    ridge = Ridge(alpha=ALPHA, random_state=42)
    ridge.fit(x_train, train["target_aqi_24h"].values)

    results = {}
    for name, part in (("val", val), ("test", test)):
        x = scl.transform(imp.transform(part[refined_cols]))
        naive = part["aqi_curr"].values
        pred = BLEND_NAIVE * naive + (1.0 - BLEND_NAIVE) * ridge.predict(x)
        results[name] = evaluate_metrics(part["target_aqi_24h"].values, pred)
        naive_metrics = evaluate_metrics(part["target_aqi_24h"].values, naive)
        print(f"[{name}] hybrid: {results[name]}")
        print(f"[{name}] persistence: {naive_metrics}")

        out = part[["station_id", "station_name", "timestamp", "split", "aqi_curr", "target_aqi_24h", "aqi_source"]].copy()
        out["prediction_naive_persistence"] = naive
        out["prediction_hybrid_6c_winning"] = pred
        target = OUT_DIR / ("final_predictions_extended.parquet" if name == "test" else "val_predictions_extended.parquet")
        target.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(target, index=False)
        print(f"Wrote {target}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results["meta"] = {"n_train": int(len(train)), "embargo_hours": 24}
    (OUT_DIR / "extended_training_metrics.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

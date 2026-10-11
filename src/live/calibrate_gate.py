"""Fix the forecast job's missing-feature gate on the VALIDATION window (never guessed, never on test).

For every validation row of the stored feature matrix, the share of the models' *core* features that are NaN (core = all
features except the groups the D1 audit showed may be absent: NOx, station weather, solar, and the station one-hots) is
computed per model; the gate is the 99th percentile of the worst of the three, rounded up to 0.01. A live row more degraded
than 99% of the rows the models were validated on is skipped, with the reason recorded.

    python -m src.live.calibrate_gate           # needs data/processed/features_extended.parquet and lightgbm
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.live import forecast, models as model_mod
from src.models.phase_6c_refinement import construct_causal_long_horizon_features
from src.models.splits import KST, VAL_END, VAL_START

FEATURES = Path(__file__).resolve().parents[2] / "data" / "processed" / "features_extended.parquet"
PERCENTILE = 99


def calibrate() -> dict:
    models = model_mod.load()
    frame = pd.read_parquet(FEATURES)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_convert(KST)
    frame = construct_causal_long_horizon_features(frame)
    val = frame[(frame["timestamp"] >= VAL_START) & (frame["timestamp"] <= VAL_END)]
    shares = pd.concat({h: val.apply(lambda row, n=names: forecast.core_missing_share(row, n), axis=1) for h, names in models.features.items()}, axis=1)
    worst = shares.max(axis=1)
    value = math.ceil(float(np.percentile(worst, PERCENTILE)) * 100) / 100
    return {
        "max_core_missing_share": value,
        "derivation": f"{PERCENTILE}th percentile of the per-row worst core-missing share over {len(val):,} validation rows "
                      f"({VAL_START:%Y-%m-%d}..{VAL_END:%Y-%m-%d}), rounded up to 0.01",
        "percentiles_of_worst_share": {str(q): round(float(np.percentile(worst, q)), 4) for q in (50, 90, 95, 99, 99.9, 100)},
        "share_of_validation_rows_with_any_core_missing": round(float((worst > 0).mean()), 4),
        "core_features": {str(h): sum(1 for c in names if not c.startswith("station_") and not c.startswith(forecast.AUDITED_ABSENT_PREFIXES))
                          for h, names in models.features.items()},
        "audited_absent_prefixes": list(forecast.AUDITED_ABSENT_PREFIXES),
    }


if __name__ == "__main__":
    result = calibrate()
    forecast.GATE_PATH.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    sys.exit(0)

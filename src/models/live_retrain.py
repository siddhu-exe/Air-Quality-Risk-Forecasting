"""Live-consistent re-fit of the three AQI models (Tier 3 decision, 2026-10-15). Run on Colab.

Same architectures, features and hyper-parameters as the frozen models; the only change is the AQI definition. Input
features (``aqi_curr``, AQI lags/rolling/cross-station) and targets both come from the AQI the live pipeline computes
(``src/features/build_live_matrix.py``), so training and serving agree.

  1h / 6h  lightgbm.Booster; the 131 feature names and the hyper-parameters are read from the frozen boosters (hash-verified),
           ``num_iterations`` is chosen by early stopping (50 rounds) on the validation window
  24h      0.5 x persistence + 0.5 x Ridge(alpha=1000) on the frozen 49 refined features (imputer -> scaler -> ridge)

Split (``src/models/splits.py``): train 2024-01-01 .. 2025-08-31 with a 24h embargo before the validation window,
validation 2025-09-01 .. 2025-10-31 (selects the iteration count only), test 2025-11-01 .. 2025-12-31 scored once.
Every score is next to persistence on the SAME recomputed AQI, with 95% day-block bootstrap CIs. The frozen models are scored
on the same rows as a reference. The retrained models are also scored on the live-masked matrix (no NOx/NO/solar, no ITO
weather) with NO refit, as the second declared view of the live-serving case.

New models go to ``models/live/`` with new versions; nothing under ``models/`` outside that folder is read for writing.

    python -m src.models.live_retrain [--horizons 1 6 24]
Environment: LIVE_FEATURES_PATH / LIVE_MASKED_FEATURES_PATH (matrices), LIVE_MODEL_DIR, LIVE_OUT_DIR, LIVE_RETRAIN_ALLOW_RESCORE=1
to score test again (otherwise a second run is refused).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.evaluation.build_metrics_table import block_bootstrap
from src.live import models as frozen
from src.models.phase_6c_refinement import construct_causal_long_horizon_features
from src.models.splits import assign_split, training_rows

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = Path(os.environ.get("LIVE_FEATURES_PATH", REPO_ROOT / "data" / "processed" / "features_live.parquet"))
MASKED_PATH = Path(
    os.environ.get("LIVE_MASKED_FEATURES_PATH", REPO_ROOT / "data" / "processed" / "features_live_masked.parquet")
)
MODEL_DIR = Path(os.environ.get("LIVE_MODEL_DIR", REPO_ROOT / "models" / "live"))
OUT_DIR = Path(os.environ.get("LIVE_OUT_DIR", REPO_ROOT / "reports" / "modeling" / "live_retrain"))
VERSIONS = {1: "aqi-1h-lgb-live-v1", 6: "aqi-6h-lgb-live-v1", 24: "aqi-24h-hybrid-live-v1"}
ALPHA, BLEND_PERSISTENCE = 1000.0, 0.5
EARLY_STOPPING_ROUNDS = 50
SMOKE = os.environ.get("LIVE_RETRAIN_SMOKE") == "1"  # code-path check only: 30 rounds, 20 resamples, never for results
N_BOOT, SEED = (20 if SMOKE else 1000), 42
KEYS = ["station_id", "timestamp"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add_station_dummies(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for name in sorted(frame["station_name"].unique()):
        out[f"station_{name.replace(' ', '_')}"] = (frame["station_name"] == name).astype(float)
    return out


def load_matrix(path: Path, long_horizon: bool) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if long_horizon:
        frame = construct_causal_long_horizon_features(frame)
    frame["split"] = assign_split(frame["timestamp"])
    return add_station_dummies(frame)


def frozen_spec() -> dict:
    """Hash-verified frozen artifacts: feature lists, LightGBM hyper-parameters, and the frozen predictors for reference."""
    frozen.verify()
    loaded = frozen.load(horizons=(1, 6, 24))
    params = {h: {k: v for k, v in b.params.items() if k != "num_iterations"} for h, b in loaded.boosters.items()}
    return {
        "loaded": loaded,
        "features": {1: loaded.features[1], 6: loaded.features[6], 24: list(loaded.features_24h)},
        "params": params,
    }


def rows_for(frame: pd.DataFrame, horizon: int) -> dict:
    target = f"target_aqi_{horizon}h"
    data = frame.dropna(subset=[target, "aqi_curr"])
    return {"train": training_rows(data), "val": data[data["split"] == "val"], "test": data[data["split"] == "test"]}


def fit_lgb(train: pd.DataFrame, val: pd.DataFrame, features: list[str], target: str, params: dict):
    import lightgbm as lgb

    dtrain = lgb.Dataset(train[features], label=train[target])
    dval = lgb.Dataset(val[features], label=val[target], reference=dtrain)
    booster = lgb.train(
        dict(params),
        dtrain,
        num_boost_round=30 if SMOKE else 2000,
        valid_sets=[dval],
        valid_names=["val"],
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
    )
    return booster


def fit_hybrid(train: pd.DataFrame, features: list[str], target: str):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    imputer, scaler = SimpleImputer(strategy="median"), StandardScaler()
    x = scaler.fit_transform(imputer.fit_transform(train[features]))
    ridge = Ridge(alpha=ALPHA, random_state=42).fit(x, train[target].to_numpy())
    return {"imputer": imputer, "scaler": scaler, "ridge": ridge}


def predict_hybrid(parts: dict, part: pd.DataFrame, features: list[str]) -> np.ndarray:
    ridge = parts["ridge"].predict(parts["scaler"].transform(parts["imputer"].transform(part[features])))
    return BLEND_PERSISTENCE * part["aqi_curr"].to_numpy(float) + (1 - BLEND_PERSISTENCE) * ridge


def score(part: pd.DataFrame, prediction: np.ndarray, target: str) -> dict:
    y, persistence = part[target].to_numpy(float), part["aqi_curr"].to_numpy(float)
    days = pd.to_datetime(part["timestamp"]).dt.date.values
    ci = block_bootstrap(y, prediction, persistence, days, N_BOOT, SEED)
    mae, base = float(np.abs(prediction - y).mean()), float(np.abs(persistence - y).mean())
    return {
        "n": len(part),
        "model_mae": mae,
        "persistence_mae": base,
        "skill_mae": 1 - mae / base,
        "skill_ci_lo": float(ci["skill_mae_ci_lo"]),
        "skill_ci_hi": float(ci["skill_mae_ci_hi"]),
    }


def frozen_predict(spec: dict, horizon: int, part: pd.DataFrame) -> np.ndarray:
    loaded = spec["loaded"]
    if horizon == 24:
        return frozen.predict_24h(loaded, part)
    return loaded.boosters[horizon].predict(part[spec["features"][horizon]])


def main(horizons: list[int]) -> int:
    marker = OUT_DIR / "test_scored.json"
    if marker.exists() and os.environ.get("LIVE_RETRAIN_ALLOW_RESCORE") != "1":
        raise SystemExit(
            f"{marker} exists: the test window was already scored once. Set LIVE_RETRAIN_ALLOW_RESCORE=1 only if you mean it."
        )
    spec = frozen_spec()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    plain, masked = load_matrix(FEATURES_PATH, True), load_matrix(MASKED_PATH, True)
    if len(plain) != len(masked) or not (plain[KEYS].to_numpy() == masked[KEYS].to_numpy()).all():
        raise SystemExit("the plain and masked matrices do not have identical rows")
    if "aqi_source" in plain and set(plain["aqi_source"].dropna().unique()) != {"recomputed"}:
        raise SystemExit("the live matrix must carry only recomputed AQI")

    records, manifest_models, predictions = [], {}, {}
    for horizon in horizons:
        target, version = f"target_aqi_{horizon}h", VERSIONS[horizon]
        features = spec["features"][horizon]
        missing = [c for c in features if c not in plain.columns]
        if missing:
            raise SystemExit(f"{horizon}h: frozen features absent from the live matrix: {missing[:5]}")
        sets, sets_masked = rows_for(plain, horizon), rows_for(masked, horizon)
        if horizon in (1, 6):
            import lightgbm as lgb

            fitted = fit_lgb(sets["train"], sets["val"], features, target, spec["params"][horizon])
            best = int(fitted.best_iteration)
            # keep exactly the selected trees, as the frozen boosters do (num_trees == best_iteration)
            model = lgb.Booster(model_str=fitted.model_to_string(num_iteration=best))
            model.best_iteration = best
            predict = lambda part, m=model, f=features: m.predict(part[f])  # noqa: E731
            artifact, detail = (
                MODEL_DIR / f"{version}.joblib",
                {"best_iteration": best, "n_trees": int(model.num_trees()), "params": spec["params"][horizon]},
            )
            joblib.dump(model, artifact)
            model.save_model(str(MODEL_DIR / f"{version}.txt"))
            files = [artifact, MODEL_DIR / f"{version}.txt"]
        else:
            parts = fit_hybrid(sets["train"], features, target)
            predict = lambda part, p=parts, f=features: predict_hybrid(p, part, f)  # noqa: E731
            folder = MODEL_DIR / version
            folder.mkdir(exist_ok=True)
            for name, obj in {
                "model": parts["ridge"],
                "imputer": parts["imputer"],
                "scaler": parts["scaler"],
                "features": features,
            }.items():
                joblib.dump(obj, folder / f"{name}.joblib")
            files, detail = sorted(folder.glob("*.joblib")), {"alpha": ALPHA, "blend_persistence": BLEND_PERSISTENCE}
        for split in ("val", "test"):
            for view, data in (("unmasked", sets), ("live-masked", sets_masked)):
                part = data[split]
                pred = predict(part)
                records.append(
                    {
                        "horizon": f"{horizon}h",
                        "split": split,
                        "inputs": view,
                        "model": version,
                        **score(part, pred, target),
                    }
                )
                if view == "unmasked":
                    predictions[(horizon, split)] = part[[*KEYS, "aqi_curr", target]].assign(prediction=pred)
            part = sets[split]
            reference = frozen_predict(spec, horizon, part)
            records.append(
                {
                    "horizon": f"{horizon}h",
                    "split": split,
                    "inputs": "unmasked",
                    "model": frozen.VERSIONS[horizon] + " (frozen, reference)",
                    **score(part, reference, target),
                }
            )
            predictions[(horizon, split)] = predictions[(horizon, split)].assign(frozen_prediction=reference)
        manifest_models[version] = {
            "horizon_hours": horizon,
            "files": {f.relative_to(MODEL_DIR).as_posix(): sha256(f) for f in files},
            "n_train": int(len(sets["train"])),
            "n_val": int(len(sets["val"])),
            "n_features": len(features),
            "features": features,
            **detail,
        }
        print(
            f"fitted {version}: "
            + "; ".join(
                f"{r['split']}/{r['inputs']} skill {r['skill_mae']:+.3f}"
                for r in records
                if r["model"] == version and r["horizon"] == f"{horizon}h"
            ),
            flush=True,
        )

    table = pd.DataFrame(records)
    table.to_csv(OUT_DIR / "live_retrain_metrics.csv", index=False)
    for (horizon, split), frame in predictions.items():
        frame.to_parquet(OUT_DIR / f"predictions_{horizon}h_{split}.parquet", index=False)
    import lightgbm
    import sklearn

    manifest = {
        "created": pd.Timestamp.now(tz="UTC").isoformat(),
        "aqi_definition": "recomputed (compute_aqi rolling_subindex_mean on QC'd pollutants)",
        "train_window": "2024-01-01 .. 2025-08-31 minus 24h embargo",
        "validation": "2025-09-01 .. 2025-10-31 (iteration count only)",
        "test": "2025-11-01 .. 2025-12-31, scored once",
        "frozen_hashes": {k: v for k, v in frozen.verify().items()},
        "matrices": {"plain": sha256(FEATURES_PATH), "masked": sha256(MASKED_PATH)},
        "libraries": {
            "python": platform.python_version(),
            "lightgbm": lightgbm.__version__,
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "models": manifest_models,
    }
    (MODEL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    marker.write_text(json.dumps({"scored": pd.Timestamp.now(tz="UTC").isoformat(), "horizons": horizons}))
    write_report(table)
    print(
        table[
            [
                "horizon",
                "split",
                "inputs",
                "model",
                "n",
                "model_mae",
                "persistence_mae",
                "skill_mae",
                "skill_ci_lo",
                "skill_ci_hi",
            ]
        ]
        .round(3)
        .to_string(index=False)
    )
    return 0


def write_report(table: pd.DataFrame) -> None:
    lines = [
        "# Live-consistent retrain: recomputed AQI as input features and target",
        "",
        "Generated by `src/models/live_retrain.py`; numbers come from `live_retrain_metrics.csv`. Skill = 1 - MAE_model / MAE_persistence,",
        "persistence on the same recomputed AQI. CIs: 95% day-block bootstrap (1,000 resamples). Validation selected only the LightGBM iteration",
        "count; the test window was scored once. `live-masked` = the same fitted model on inputs without NOx/NO/solar and ITO weather (no refit).",
        "The frozen rows score the frozen models on the same recomputed rows (reference).",
        "",
        "| Horizon | Split | Inputs | Model | Rows | MAE | Persistence MAE | Skill | Skill 95% CI |",
        "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: |",
    ]
    lines += [
        f"| {r.horizon} | {r.split} | {r.inputs} | {r.model} | {r.n:,} | {r.model_mae:.3f} | {r.persistence_mae:.3f} | {r.skill_mae:+.3f} | "
        f"[{r.skill_ci_lo:+.3f}, {r.skill_ci_hi:+.3f}] |"
        for r in table.itertuples()
    ]
    (OUT_DIR / "live_retrain_metrics.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", nargs="+", type=int, default=[1, 6, 24], choices=[1, 6, 24])
    sys.exit(main(parser.parse_args().horizons))

"""
ablation_exogenous.py
======================
Ablation of exogenous feature groups for the 24h forecast (improvement plan T2.4).

Runs on `data/processed/features_exogenous.parquet` (built by
`src/features/exogenous_drivers.py`). Feature groups:

  * baseline            - curated AQI feature set (no exogenous)
  * +weather_causal     - Open-Meteo weather at t (plus 24h rolling mean)
  * +weather_oracle     - the same plus weather at t+24 (perfect forecast; an UPPER BOUND,
                          never eligible for selection)
  * +fires              - NASA FIRMS fire counts, lagged 1-3 days
  * +weather_causal+fires

Two design points that the first version got wrong:

1. **Boundary-layer height does not exist before 2024-07-01** in the Open-Meteo archive
   (100% missing Jan-Jun 2024), so median-imputing it would give the model a constant
   for a third of the training window. Two panels are run instead:
     - ``full_no_blh``  : train from 2024-01-01, boundary-layer-height columns dropped;
     - ``blh_window``   : train from 2024-07-01 (BLH available everywhere), BLH included.
2. **Two model families**, because one linear model cannot show whether weather helps:
     - ``ridge_hybrid`` : the frozen 24h model (0.5 * persistence + 0.5 * Ridge alpha=1000);
     - ``gbm_residual`` : HistGradientBoosting on ``target - aqi_curr`` added back to
                          persistence (trees see weather interactions without having to
                          extrapolate the AQI level).

Fire groups are reported as ``not_run`` (not as a copy of the baseline) when no
``fire_*`` columns exist, i.e. when no FIRMS_MAP_KEY was used.

Selection uses validation MAE over deployable groups (oracle excluded). Test is scored
once: for the single best validation configuration and for its matched baseline.
Training rows are embargoed by 24h before the validation window.

Compute profiles (``T2_PROFILE``, ``src/models/tuning.py``): ``standard`` uses fixed GBM settings;
``max`` first runs a random hyper-parameter search for ``gbm_residual`` on the *baseline* feature group of
each panel (validation MAE), then uses the tuned settings for every group of that panel, so the groups stay
comparable. Written to ``exogenous/max/``.

Output: reports/modeling/exogenous/[<profile>/]ablation.{csv,md}
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src.models.phase_6c_refinement import (
    construct_causal_long_horizon_features,
    define_feature_candidate_sets,
)
from src.models.splits import KST, assign_split, to_kst, training_rows
from src.models.tuning import get_profile, is_standard, out_dir, search_configs

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_exogenous.parquet"
FEATURE_NAMES_AB = REPO_ROOT / "models" / "24h" / "feature_names_ab.joblib"
PROFILE = get_profile()
OUT_DIR = out_dir(REPO_ROOT / "reports" / "modeling" / "exogenous")
GBM_STANDARD = {"max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 31}
ALPHA = 1000.0
BLEND_NAIVE = 0.50
BLH_START = pd.Timestamp("2024-07-01", tz=KST)
TARGET = "target_aqi_24h"
GROUPS = ["baseline", "+weather_causal", "+weather_oracle", "+fires", "+weather_causal+fires"]
ORACLE = {"+weather_oracle"}


def metrics(y_true, y_pred):
    err = y_pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "r2": float(1 - np.sum(err**2) / np.sum((y_true - y_true.mean()) ** 2)),
    }


def tune_gbm(train: pd.DataFrame, val: pd.DataFrame, cols: list[str]) -> tuple[dict, float]:
    """Random search for gbm_residual on validation MAE; returns (params incl. max_iter, val MAE)."""
    best = None
    for n, cfg in enumerate(search_configs(PROFILE["n_search"]), start=0):
        model = HistGradientBoostingRegressor(
            max_iter=PROFILE["ablation_max_iter"],
            early_stopping=False,
            random_state=42,
            **cfg,
        ).fit(train[cols], train[TARGET] - train["aqi_curr"])
        base, y = val["aqi_curr"].values, val[TARGET].values
        maes = [float(np.mean(np.abs(base + p - y))) for p in model.staged_predict(val[cols])]
        i = int(np.argmin(maes))
        print(
            f"  gbm search {n}/{PROFILE['n_search']} {cfg} -> val MAE {maes[i]:.3f} @ {i + 1} iters"
            f"{'  *' if best is None or maes[i] < best[0] else ''}",
            flush=True,
        )
        if best is None or maes[i] < best[0]:
            best = (maes[i], {**cfg, "max_iter": i + 1})
    return best[1], best[0]


def fit_predict(family: str, train: pd.DataFrame, parts: dict, cols: list[str], gbm_params: dict | None = None) -> dict:
    """Fit one family on `train`; return {split_name: prediction}."""
    if family == "ridge_hybrid":
        imputer, scaler = SimpleImputer(strategy="median"), StandardScaler()
        x = scaler.fit_transform(imputer.fit_transform(train[cols]))
        model = Ridge(alpha=ALPHA, random_state=42).fit(x, train[TARGET].values)
        return {
            name: BLEND_NAIVE * part["aqi_curr"].values
            + (1 - BLEND_NAIVE) * model.predict(scaler.transform(imputer.transform(part[cols])))
            for name, part in parts.items()
        }
    model = HistGradientBoostingRegressor(
        **(gbm_params or GBM_STANDARD),
        early_stopping=False,
        random_state=42,
    ).fit(train[cols], train[TARGET] - train["aqi_curr"])
    return {name: part["aqi_curr"].values + model.predict(part[cols]) for name, part in parts.items()}


def main() -> None:
    frame = pd.read_parquet(FEATURES_PATH)
    frame = construct_causal_long_horizon_features(frame)
    frame["split"] = assign_split(frame["timestamp"])
    frame = frame.dropna(subset=[TARGET])

    refined = [
        c
        for c in define_feature_candidate_sets(joblib.load(FEATURE_NAMES_AB))["Set Refined (Curated 54 Feats)"]
        if c in frame.columns
    ]
    wx_all = [c for c in frame.columns if c.startswith("wx_")]
    fire_cols = [c for c in frame.columns if c.startswith("fire_")]
    have_fires = len(fire_cols) > 0
    if not have_fires:
        print("No fire_* columns: fire groups will be reported as not_run.")

    full_train = training_rows(frame)
    val = frame[frame["split"] == "val"]
    test = frame[frame["split"] == "test"]
    parts = {"val": val, "test": test}
    y = {"val": val[TARGET].values, "test": test[TARGET].values}

    panels = {
        "full_no_blh": (
            full_train,
            [c for c in wx_all if "boundary_layer" not in c],
        ),
        "blh_window": (
            full_train[to_kst(full_train["timestamp"]) >= BLH_START],
            wx_all,
        ),
    }

    records, preds_cache, tuned = [], {}, {}
    for panel, (train, wx_panel) in panels.items():
        wx_causal = [c for c in wx_panel if not c.endswith("_oracle")]
        group_cols = {
            "baseline": refined,
            "+weather_causal": refined + wx_causal,
            "+weather_oracle": refined + wx_panel,
            "+fires": refined + fire_cols,
            "+weather_causal+fires": refined + wx_causal + fire_cols,
        }
        gbm_params = None
        if not is_standard():
            gbm_params, tuned_mae = tune_gbm(train, val, refined)
            tuned[panel] = gbm_params
            print(f"[{panel}] tuned gbm_residual settings {gbm_params} (baseline val MAE {tuned_mae:.3f})", flush=True)
        for family in ("ridge_hybrid", "gbm_residual"):
            base_val_mae = None
            for group in GROUPS:
                cols = group_cols[group]
                row = {"panel": panel, "family": family, "group": group, "n_train": int(len(train))}
                if "fires" in group and not have_fires:
                    records.append({**row, "n_features": None, "split": "val", "status": "not_run"})
                    continue
                preds = fit_predict(family, train, parts, cols, gbm_params)
                preds_cache[(panel, family, group)] = preds
                m = metrics(y["val"], preds["val"])
                if group == "baseline":
                    base_val_mae = m["mae"]
                records.append(
                    {
                        **row,
                        "n_features": len(cols),
                        "split": "val",
                        "status": "ok",
                        "mae": round(m["mae"], 3),
                        "rmse": round(m["rmse"], 3),
                        "r2": round(m["r2"], 3),
                        "mae_delta_vs_baseline": round(m["mae"] - base_val_mae, 3),
                        "deployable": group not in ORACLE,
                    }
                )
                print(
                    f"[{panel}/{family}] {group:24s} n_feat={len(cols):3d} "
                    f"val MAE {m['mae']:.3f} RMSE {m['rmse']:.3f} (d_vs_base {m['mae'] - base_val_mae:+.3f})",
                    flush=True,
                )

    table = pd.DataFrame(records)
    ok = table[(table["status"] == "ok") & (table["deployable"] == True)]  # noqa: E712
    best = ok.loc[ok["mae"].idxmin()]
    print(f"Best deployable on validation: {best.panel}/{best.family}/{best.group} (MAE {best.mae})")

    # test: scored once for the validation-selected config and its matched baseline
    test_rows = []
    for group in dict.fromkeys([best.group, "baseline"]):
        key = (best.panel, best.family, group)
        m = metrics(y["test"], preds_cache[key]["test"])
        test_rows.append(
            {
                "panel": best.panel,
                "family": best.family,
                "group": group,
                "n_train": int(best.n_train),
                "split": "test",
                "status": "ok",
                "mae": round(m["mae"], 3),
                "rmse": round(m["rmse"], 3),
                "r2": round(m["r2"], 3),
                "deployable": True,
            }
        )
    persistence_test = metrics(y["test"], test["aqi_curr"].values)
    table = pd.concat([table, pd.DataFrame(test_rows)], ignore_index=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_DIR / "ablation.csv", index=False)

    lines = [
        "# Exogenous-driver ablation (24h forecast)",
        "",
        "Weather = Open-Meteo ERA5. `+weather_oracle` uses weather at t+24 and is an **upper bound",
        "only** (never selected; a real deployment needs forecast weather). Boundary-layer height",
        "is unavailable before 2024-07-01, so it is only used in the `blh_window` panel.",
        "Fire groups need a NASA FIRMS key; they are `not_run` when no `fire_*` columns exist.",
        f"Profile: `{PROFILE['name']}`"
        + (
            ""
            if is_standard()
            else "; `gbm_residual` hyper-parameters tuned on the baseline group of each panel: "
            + "; ".join(f"{k}: `{v}`" for k, v in tuned.items())
        )
        + ".",
        "",
        "## Validation (2025-09-01..10-31) - lower MAE is better",
        "",
        "| Panel | Family | Group | # feats | Train n | Val MAE | Val RMSE | Val R² | ΔMAE vs baseline |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, r in table[table["split"] == "val"].iterrows():
        if r.status != "ok":
            lines.append(
                f"| {r.panel} | {r.family} | {r.group} | - | {r.n_train:,} | not run | not run | not run | - |"
            )
        else:
            lines.append(
                f"| {r.panel} | {r.family} | {r.group} | {int(r.n_features)} | {r.n_train:,} | {r.mae} | "
                f"{r.rmse} | {r.r2} | {r.mae_delta_vs_baseline:+.3f} |"
            )
    lines += [
        "",
        f"**Best deployable on validation:** `{best.panel}` / `{best.family}` / `{best.group}` (val MAE {best.mae}).",
        "",
        "## Test (2025-11-01..12-31), scored once",
        "",
        "| Panel | Family | Group | Test MAE | Test RMSE | Test R² |",
        "| :--- | :--- | :--- | ---: | ---: | ---: |",
    ]
    for r in test_rows:
        lines.append(f"| {r['panel']} | {r['family']} | {r['group']} | {r['mae']} | {r['rmse']} | {r['r2']} |")
    lines.append(
        f"| - | persistence | aqi_now | {persistence_test['mae']:.3f} | "
        f"{persistence_test['rmse']:.3f} | {persistence_test['r2']:.3f} |"
    )
    (OUT_DIR / "ablation.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_DIR / 'ablation.md'}")


if __name__ == "__main__":
    main()

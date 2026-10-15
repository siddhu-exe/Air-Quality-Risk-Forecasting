"""
train_pm25_forecast.py
=======================
Forecast raw PM2.5 (ug/m3) at 1h/6h/24h as an alternative target (plan T2.3).

Motivation: the official AQI target is a 24-hour rolling average with lag-1
autocorrelation ~0.998, so persistence is nearly unbeatable there. Raw PM2.5
has real hourly dynamics, so a model has room to add skill over persistence
(``pred = pm25_now``).

Model: histogram gradient-boosting regressor (scikit-learn) on the extended
2024-2025 feature matrix, chronological split from ``src/models/splits.py``:
  train 2024-01-01..2025-08-31 (minus a 24h embargo), val 2025-09-01..10-31,
  test 2025-11-01..12-31.

Model selection (validation only, per horizon). Four variants are fitted and the
one with the lowest validation MAE is kept; test is scored once for that variant:
  * target form: ``level`` (predict PM2.5 at t+h) or ``residual``
    (predict PM2.5(t+h) - PM2.5(t), added back to the persistence value),
  * calendar features: with / without the raw & cyclical calendar columns.

Compute profiles (``T2_PROFILE``, see ``src/models/tuning.py``):
  * standard: fixed settings (400 iterations), as in the accepted results.
  * max: the boosting iteration count is chosen on validation for every variant, then a
    random hyper-parameter search (default config always included) is run for the selected
    variant on validation MAE; more bootstrap resamples. Written to ``pm25/max/``.

Outputs
-------
  reports/modeling/pm25/[<profile>/]pm25_forecast_metrics.{csv,md}   (selected variant, val + test)
  reports/modeling/pm25/[<profile>/]variant_selection.csv            (all fits, validation)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from src.evaluation.build_metrics_table import block_bootstrap
from src.models.live_overrides import export, export_dir, matrix_path, prune_columns, report_dir
from src.models.splits import assign_split, model_feature_columns, training_rows
from src.models.tuning import DEFAULT_CONFIG, get_profile, is_standard, out_dir, search_configs

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = matrix_path(REPO_ROOT / "data" / "processed" / "features_extended.parquet")
PROFILE = get_profile()
OUT_DIR = report_dir(out_dir(REPO_ROOT / "reports" / "modeling" / "pm25"))
HORIZONS = [1, 6, 24]
VARIANTS = [("level", True), ("level", False), ("residual", True), ("residual", False)]
N_BOOT = PROFILE["n_boot"]
MAX_ITER = PROFILE["pm25_max_iter"]
SEED = 42


def metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "r2": float(1 - np.sum(err**2) / np.sum((y_true - y_true.mean()) ** 2)),
    }


def fit_variant(train: pd.DataFrame, target: str, cols: list[str], form: str, cfg: dict | None = None):
    cfg = DEFAULT_CONFIG if cfg is None else cfg
    y = train[target] - train["pm25_curr"] if form == "residual" else train[target]
    model = HistGradientBoostingRegressor(
        max_iter=MAX_ITER, early_stopping=False, random_state=42, **cfg,
    )
    return model.fit(train[cols], y)


def predict_variant(model, part: pd.DataFrame, cols: list[str], form: str) -> np.ndarray:
    pred = model.predict(part[cols])
    return pred + part["pm25_curr"].values if form == "residual" else pred


def staged_best(model, val: pd.DataFrame, cols: list[str], target: str, form: str) -> tuple[int, float]:
    """(index, MAE) of the boosting iteration with the lowest validation MAE."""
    y = val[target].values
    base = val["pm25_curr"].values if form == "residual" else 0.0
    maes = [float(np.mean(np.abs(p + base - y))) for p in model.staged_predict(val[cols])]
    best = int(np.argmin(maes))
    return best, maes[best]


def predict_staged(model, part: pd.DataFrame, cols: list[str], form: str, index: int) -> np.ndarray:
    for i, pred in enumerate(model.staged_predict(part[cols])):
        if i == index:
            return pred + part["pm25_curr"].values if form == "residual" else pred
    raise IndexError(index)


def main() -> None:
    frame = pd.read_parquet(FEATURES_PATH)
    frame["split"] = assign_split(frame["timestamp"])
    cols_with_cal = model_feature_columns(frame, drop_calendar=False)
    cols_no_cal = model_feature_columns(frame, drop_calendar=True)
    print(f"profile={PROFILE['name']}: {len(cols_with_cal)} features with calendar, "
          f"{len(cols_no_cal)} without", flush=True)
    standard = is_standard()

    selection_rows, records = [], []
    for horizon in HORIZONS:
        target = f"target_pm25_{horizon}h"
        data = frame.dropna(subset=[target, "pm25_curr"])
        train = training_rows(data)
        val = data[data["split"] == "val"]
        test = data[data["split"] == "test"]
        persistence_val = metrics(val[target].values, val["pm25_curr"].values)["mae"]

        # stage 1: the four variants with the default config
        fitted = {}
        for form, use_cal in VARIANTS:
            cols = prune_columns(train, cols_with_cal if use_cal else cols_no_cal)
            model = fit_variant(train, target, cols, form)
            if standard:
                index, val_mae = None, metrics(val[target].values,
                                               predict_variant(model, val, cols, form))["mae"]
            else:
                index, val_mae = staged_best(model, val, cols, target, form)
            fitted[(form, use_cal)] = (model, cols, val_mae, index, DEFAULT_CONFIG)
            selection_rows.append({
                "horizon": f"{horizon}h", "stage": "variant", "target_form": form, "calendar": use_cal,
                "iterations": MAX_ITER if standard else index + 1, "params": json.dumps(DEFAULT_CONFIG),
                "val_mae": round(val_mae, 3), "val_persistence_mae": round(persistence_val, 3),
                "val_mae_skill": round(1 - val_mae / persistence_val, 4),
            })
            print(f"[{horizon}h] {form:8s} calendar={use_cal!s:5s} val MAE {val_mae:.3f} "
                  f"(persistence {persistence_val:.3f})", flush=True)

        best_key = min(fitted, key=lambda k: fitted[k][2])
        form, use_cal = best_key

        # stage 2 (non-standard profiles): hyper-parameter search for the selected variant
        if not standard:
            cols = fitted[best_key][1]
            for n, cfg in enumerate(search_configs(PROFILE["n_search"])[1:], start=1):
                model = fit_variant(train, target, cols, form, cfg)
                index, val_mae = staged_best(model, val, cols, target, form)
                selection_rows.append({
                    "horizon": f"{horizon}h", "stage": "search", "target_form": form, "calendar": use_cal,
                    "iterations": index + 1, "params": json.dumps(cfg),
                    "val_mae": round(val_mae, 3), "val_persistence_mae": round(persistence_val, 3),
                    "val_mae_skill": round(1 - val_mae / persistence_val, 4),
                })
                improved = val_mae < fitted[best_key][2]
                print(f"[{horizon}h] search {n}/{PROFILE['n_search']} {cfg} -> val MAE {val_mae:.3f}"
                      f"{'  *' if improved else ''}", flush=True)
                if improved:
                    fitted[best_key] = (model, cols, val_mae, index, cfg)

        model, cols, _, index, cfg = fitted[best_key]
        if export_dir() is not None:
            if not standard:
                raise SystemExit("LIVE_EXPORT_DIR is only supported with T2_PROFILE=standard")
            export(f"pm25-{horizon}h-hgb-live-v1", {"model": model, "columns": cols, "target_form": form, "horizon": horizon},
                   {"horizon_hours": horizon, "target_form": form, "calendar": bool(use_cal), "iterations": MAX_ITER, "params": cfg,
                    "n_features": len(cols), "matrix": str(FEATURES_PATH.name)})
        for split_name, part in (("val", val), ("test", test)):
            pred = (predict_variant(model, part, cols, form) if standard
                    else predict_staged(model, part, cols, form, index))
            persistence = part["pm25_curr"].values
            y = part[target].values
            m, p = metrics(y, pred), metrics(y, persistence)
            ci = block_bootstrap(
                y, pred, persistence, pd.to_datetime(part["timestamp"]).dt.date.values,
                N_BOOT, SEED,
            )
            records.append({
                "profile": PROFILE["name"],
                "horizon": f"{horizon}h", "split": split_name, "n": len(part),
                "target_form": form, "calendar": use_cal,
                "iterations": MAX_ITER if standard else index + 1, "params": json.dumps(cfg),
                "model_mae": round(m["mae"], 3), "model_rmse": round(m["rmse"], 3),
                "model_r2": round(m["r2"], 3),
                "persistence_mae": round(p["mae"], 3), "persistence_rmse": round(p["rmse"], 3),
                "skill_mae": round(1 - m["mae"] / p["mae"], 4),
                "skill_mae_ci_lo": round(ci["skill_mae_ci_lo"], 4),
                "skill_mae_ci_hi": round(ci["skill_mae_ci_hi"], 4),
                "skill_rmse": round(1 - m["rmse"] / p["rmse"], 4),
            })
            print(f"[{horizon}h {split_name}] selected {form}/cal={use_cal}: MAE {m['mae']:.2f} vs "
                  f"persistence {p['mae']:.2f} (skill {records[-1]['skill_mae']:+.3f})", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(records)
    table.to_csv(OUT_DIR / "pm25_forecast_metrics.csv", index=False)
    pd.DataFrame(selection_rows).to_csv(OUT_DIR / "variant_selection.csv", index=False)

    lines = [
        "# Raw PM2.5 forecast metrics",
        "",
        f"Profile: `{PROFILE['name']}`. HistGradientBoosting on the extended 2024-2025 feature matrix;",
        "persistence = `pm25_now`. Skill = 1 - metric_model / metric_persistence. The variant (target",
        "form, calendar features)"
        + (" and the hyper-parameters are" if not standard else " is")
        + " chosen per horizon on validation MAE only;",
        "test is scored once. Skill CIs are 95% day-block bootstrap intervals "
        f"({N_BOOT:,} resamples).",
        "",
        "| Horizon | Split | N | Variant | Model MAE | Persistence MAE | MAE skill | Skill 95% CI | RMSE skill |",
        "| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |",
    ]
    for _, r in table.iterrows():
        variant = f"{r.target_form}{'+cal' if r.calendar else ''}"
        lines.append(
            f"| {r.horizon} | {r.split} | {r.n:,} | {variant} | {r.model_mae} | {r.persistence_mae} | "
            f"{r.skill_mae:+.4f} | [{r.skill_mae_ci_lo:+.3f}, {r.skill_mae_ci_hi:+.3f}] | {r.skill_rmse:+.4f} |"
        )
    lines += ["", "Selected settings (chosen on validation):", ""]
    for _, r in table[table["split"] == "val"].iterrows():
        lines.append(f"- {r.horizon}: {r.iterations} iterations, `{r.params}`")
    (OUT_DIR / "pm25_forecast_metrics.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_DIR / 'pm25_forecast_metrics.md'}")


if __name__ == "__main__":
    main()

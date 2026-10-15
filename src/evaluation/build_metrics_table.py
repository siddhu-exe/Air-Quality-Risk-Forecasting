"""Single source of truth for the project's headline forecast metrics.

Every MAE / RMSE / R2 number quoted in the README or docs should come from
the CSV this script writes. It reads the frozen test-set predictions for the
1h, 6h and 24h models, scores each final model next to the naive-persistence
reference, and reports a skill score against that reference.

Usage (from the repo root):

    ./venv/bin/python src/evaluation/build_metrics_table.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTREME_THRESHOLD = 300.0
OUT_CSV = REPO_ROOT / "reports" / "metrics" / "headline_metrics.csv"
OUT_MD = REPO_ROOT / "reports" / "metrics" / "headline_metrics.md"


@dataclass(frozen=True)
class HorizonSpec:
    """Maps one horizon's predictions file onto a common schema."""

    horizon: str
    model_label: str
    path: Path
    truth_col: str
    pred_col: str
    persistence_col: str
    timestamp_col: str = "timestamp"


SPECS = [
    HorizonSpec(
        horizon="1h",
        model_label="Tuned LightGBM",
        path=REPO_ROOT / "data/Artifacts/1h/predictions_1h_test.parquet",
        truth_col="y_true",
        pred_col="y_pred",
        persistence_col="naive_pred",
    ),
    HorizonSpec(
        horizon="6h",
        model_label="Tuned LightGBM",
        path=REPO_ROOT / "data/Artifacts/6h/predictions_6h_test.parquet",
        truth_col="y_true",
        pred_col="y_pred",
        persistence_col="naive_pred",
    ),
    HorizonSpec(
        horizon="24h",
        model_label="50/50 Hybrid (Persistence + Ridge)",
        path=REPO_ROOT / "reports/modeling/24h/final/final_predictions.parquet",
        truth_col="target_aqi_24h",
        pred_col="prediction_hybrid_6c_winning",
        persistence_col="prediction_naive_persistence",
    ),
    HorizonSpec(
        horizon="24h",
        model_label="50/50 Hybrid, +2024 winters (extended train)",
        path=REPO_ROOT / "reports/modeling/24h/final/final_predictions_extended.parquet",
        truth_col="target_aqi_24h",
        pred_col="prediction_hybrid_6c_winning",
        persistence_col="prediction_naive_persistence",
    ),
]


def load_frame(spec: HorizonSpec) -> pd.DataFrame:
    if not spec.path.exists():
        raise FileNotFoundError(f"Missing predictions for {spec.horizon}: {spec.path}")
    df = pd.read_parquet(spec.path)
    required = {spec.truth_col, spec.pred_col, spec.persistence_col, spec.timestamp_col}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"{spec.path.name} is missing columns: {sorted(missing)}")
    out = df[[spec.timestamp_col, spec.truth_col, spec.pred_col, spec.persistence_col]].copy()
    out.columns = ["timestamp", "y_true", "y_pred", "y_persist"]
    out = out.dropna(subset=["timestamp", "y_true", "y_pred", "y_persist"])
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    out["day"] = out["timestamp"].dt.date
    return out.reset_index(drop=True)


def point_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    denom = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float(1.0 - np.sum(err**2) / denom) if denom > 0 else float("nan")
    mask = y_true >= EXTREME_THRESHOLD
    mae_extreme = float(np.mean(np.abs(err[mask]))) if mask.any() else float("nan")
    return {
        "n": int(y_true.size),
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "bias": float(np.mean(err)),
        "mae_extreme": mae_extreme,
    }


def block_bootstrap(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_persist: np.ndarray,
    days: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict:
    """95% CI for MAE, RMSE and the two skill scores, resampling whole days."""
    rng = np.random.default_rng(seed)
    unique_days = np.unique(days)
    index_by_day = {d: np.flatnonzero(days == d) for d in unique_days}
    n_days = unique_days.size

    mae_s, rmse_s, sk_mae, sk_rmse = [], [], [], []
    for _ in range(n_boot):
        picked = rng.choice(unique_days, size=n_days, replace=True)
        idx = np.concatenate([index_by_day[d] for d in picked])
        yt, yp, yb = y_true[idx], y_pred[idx], y_persist[idx]
        m_model = float(np.mean(np.abs(yp - yt)))
        m_pers = float(np.mean(np.abs(yb - yt)))
        r_model = float(np.sqrt(np.mean((yp - yt) ** 2)))
        r_pers = float(np.sqrt(np.mean((yb - yt) ** 2)))
        mae_s.append(m_model)
        rmse_s.append(r_model)
        sk_mae.append(1.0 - m_model / m_pers)
        sk_rmse.append(1.0 - r_model / r_pers)

    def ci(values: list[float]) -> tuple[float, float]:
        lo, hi = np.percentile(values, [2.5, 97.5])
        return float(lo), float(hi)

    mae_lo, mae_hi = ci(mae_s)
    rmse_lo, rmse_hi = ci(rmse_s)
    skm_lo, skm_hi = ci(sk_mae)
    skr_lo, skr_hi = ci(sk_rmse)
    return {
        "mae_ci_lo": mae_lo,
        "mae_ci_hi": mae_hi,
        "rmse_ci_lo": rmse_lo,
        "rmse_ci_hi": rmse_hi,
        "skill_mae_ci_lo": skm_lo,
        "skill_mae_ci_hi": skm_hi,
        "skill_rmse_ci_lo": skr_lo,
        "skill_rmse_ci_hi": skr_hi,
    }


def build_rows(n_boot: int, seed: int) -> pd.DataFrame:
    rows = []
    for spec in SPECS:
        df = load_frame(spec)
        y_true = df["y_true"].to_numpy(dtype=float)
        y_pred = df["y_pred"].to_numpy(dtype=float)
        y_persist = df["y_persist"].to_numpy(dtype=float)
        days = df["day"].to_numpy()

        persist_metrics = point_metrics(y_true, y_persist)
        for label, pred in ((spec.model_label, y_pred), ("Naive persistence", y_persist)):
            m = point_metrics(y_true, pred)
            is_persist = label == "Naive persistence"
            skill_mae = 1.0 - m["mae"] / persist_metrics["mae"] if not is_persist else 0.0
            skill_rmse = 1.0 - m["rmse"] / persist_metrics["rmse"] if not is_persist else 0.0
            row = {"horizon": spec.horizon, "model": label, **m}
            row["skill_mae"] = skill_mae
            row["skill_rmse"] = skill_rmse
            row.update(block_bootstrap(y_true, pred, y_persist, days, n_boot=n_boot, seed=seed))
            rows.append(row)

    columns = [
        "horizon",
        "model",
        "n",
        "mae",
        "mae_ci_lo",
        "mae_ci_hi",
        "rmse",
        "rmse_ci_lo",
        "rmse_ci_hi",
        "r2",
        "bias",
        "mae_extreme",
        "skill_mae",
        "skill_mae_ci_lo",
        "skill_mae_ci_hi",
        "skill_rmse",
        "skill_rmse_ci_lo",
        "skill_rmse_ci_hi",
    ]
    # Several models can share a horizon; the persistence reference is then identical, keep one.
    return pd.DataFrame(rows)[columns].drop_duplicates().reset_index(drop=True)


def write_csv(df: pd.DataFrame) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.round(4).to_csv(OUT_CSV, index=False)


def format_markdown(df: pd.DataFrame) -> str:
    def f(value: float, digits: int = 2) -> str:
        return "n/a" if pd.isna(value) else f"{value:.{digits}f}"

    lines = [
        "# Headline metrics (single source of truth)",
        "",
        "Generated by `src/evaluation/build_metrics_table.py` from the frozen test-set",
        "predictions. The naive-persistence reference (`pred = aqi_now`) is shown for",
        "every horizon; skill = 1 - metric_model / metric_persistence, so a positive",
        "skill means the model beats persistence. Confidence intervals are 95% day-block",
        "bootstrap intervals (whole days resampled with replacement).",
        "",
        "| Horizon | Model | N | MAE | MAE 95% CI | RMSE | RMSE 95% CI | R² | Bias | MAE (AQI≥300) | MAE skill | RMSE skill |",
        "| :--- | :--- | ---: | ---: | :---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, r in df.iterrows():
        row = "| {horizon} | {model} | {n} | {mae} | [{mlo}, {mhi}] | {rmse} | [{rlo}, {rhi}] | {r2} | {bias} | {ext} | {skm} | {skr} |".format(
            horizon=r["horizon"],
            model=r["model"],
            n=int(r["n"]),
            mae=f(r["mae"]),
            mlo=f(r["mae_ci_lo"]),
            mhi=f(r["mae_ci_hi"]),
            rmse=f(r["rmse"]),
            rlo=f(r["rmse_ci_lo"]),
            rhi=f(r["rmse_ci_hi"]),
            r2=f(r["r2"], 3),
            bias=f(r["bias"]),
            ext=f(r["mae_extreme"], 1),
            skm=f(r["skill_mae"], 3),
            skr=f(r["skill_rmse"], 3),
        )
        lines.append(row)
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = build_rows(n_boot=args.n_boot, seed=args.seed)
    write_csv(df)
    OUT_MD.write_text(format_markdown(df))
    print(f"Wrote {OUT_CSV.relative_to(REPO_ROOT)} and {OUT_MD.relative_to(REPO_ROOT)}")
    print(df[["horizon", "model", "mae", "rmse", "r2", "skill_mae", "skill_rmse"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()

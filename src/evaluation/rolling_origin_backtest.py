"""
rolling_origin_backtest.py
===========================
Expanding-window (rolling-origin) backtest of the frozen 24h hybrid across
winters, so the headline skill is not a single-test-window artefact.

Folds
-----
  * winter 2024: train < 2024-11-01, test 2024-11-01..2024-12-31 (recomputed AQI)
  * winter 2025: train < 2025-11-01, test 2025-11-01..2025-12-31 (official AQI)

The model architecture is identical to the frozen 24h model (50/50 blend of
persistence and Ridge alpha=1000 on the curated feature set); only the training
cut-off moves. Reported per fold and as mean ± std of the persistence skill.

Outputs
-------
  reports/modeling/24h/rolling_origin_backtest.csv
  reports/modeling/24h/rolling_origin_backtest.md
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src.evaluation.build_metrics_table import block_bootstrap
from src.models.phase_6c_refinement import (
    construct_causal_long_horizon_features,
    define_feature_candidate_sets,
)
from src.models.splits import EMBARGO_HOURS, purge_train_tail
from src.models.tuning import get_profile, out_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_extended.parquet"
FEATURE_NAMES_AB = REPO_ROOT / "models" / "24h" / "feature_names_ab.joblib"
OUT_DIR = out_dir(REPO_ROOT / "reports" / "modeling" / "24h")
KST = "Asia/Kolkata"
ALPHA = 1000.0
BLEND_NAIVE = 0.50
N_BOOT = get_profile()["n_boot"]
SEED = 42


@dataclass(frozen=True)
class Fold:
    name: str
    test_start: str
    test_end: str


FOLDS = [
    Fold("winter_2024", "2024-11-01", "2024-12-31 23:59:59"),
    Fold("winter_2025", "2025-11-01", "2025-12-31 23:59:59"),
]


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "r2": float(1.0 - np.sum(err**2) / np.sum((y_true - y_true.mean()) ** 2)),
    }


def main() -> None:
    frame = pd.read_parquet(FEATURES_PATH)
    frame = construct_causal_long_horizon_features(frame)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.dropna(subset=["target_aqi_24h"])

    refined_cols = [
        c
        for c in define_feature_candidate_sets(joblib.load(FEATURE_NAMES_AB))["Set Refined (Curated 54 Feats)"]
        if c in frame.columns
    ]

    records = []
    for fold in FOLDS:
        start = pd.Timestamp(fold.test_start, tz=KST)
        end = pd.Timestamp(fold.test_end, tz=KST)
        # 24h embargo: a training row issued in the last 24h before `start` has its label inside the test window
        train = purge_train_tail(frame[frame["target_aqi_24h"].notna()], start, EMBARGO_HOURS)
        test = frame[(frame["timestamp"] >= start) & (frame["timestamp"] <= end)]
        test = test[test["target_aqi_24h"].notna()]

        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        x_train = scaler.fit_transform(imputer.fit_transform(train[refined_cols]))
        ridge = Ridge(alpha=ALPHA, random_state=42).fit(x_train, train["target_aqi_24h"].values)

        x_test = scaler.transform(imputer.transform(test[refined_cols]))
        naive = test["aqi_curr"].values
        hybrid = BLEND_NAIVE * naive + (1.0 - BLEND_NAIVE) * ridge.predict(x_test)

        m_hybrid = metrics(test["target_aqi_24h"].values, hybrid)
        m_naive = metrics(test["target_aqi_24h"].values, naive)
        ci = block_bootstrap(
            test["target_aqi_24h"].values,
            hybrid,
            naive,
            test["timestamp"].dt.date.values,
            N_BOOT,
            SEED,
        )
        records.append(
            {
                "fold": fold.name,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "n_train": int(len(train)),
                "n_test": int(len(test)),
                "aqi_source": test["aqi_source"].mode().iat[0],
                "hybrid_mae": round(m_hybrid["mae"], 3),
                "hybrid_rmse": round(m_hybrid["rmse"], 3),
                "hybrid_r2": round(m_hybrid["r2"], 3),
                "persistence_mae": round(m_naive["mae"], 3),
                "persistence_rmse": round(m_naive["rmse"], 3),
                "skill_mae": round(1 - m_hybrid["mae"] / m_naive["mae"], 4),
                "skill_rmse": round(1 - m_hybrid["rmse"] / m_naive["rmse"], 4),
                "skill_mae_ci_lo": round(ci["skill_mae_ci_lo"], 4),
                "skill_mae_ci_hi": round(ci["skill_mae_ci_hi"], 4),
            }
        )
        print(
            f"[{fold.name}] n_train={len(train):,} n_test={len(test):,} "
            f"skill_mae={records[-1]['skill_mae']:+.4f} skill_rmse={records[-1]['skill_rmse']:+.4f}"
        )

    table = pd.DataFrame(records)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_DIR / "rolling_origin_backtest.csv", index=False)

    mean_mae = table["skill_mae"].mean()
    std_mae = table["skill_mae"].std(ddof=0)
    mean_rmse = table["skill_rmse"].mean()
    std_rmse = table["skill_rmse"].std(ddof=0)

    lines = [
        "# Rolling-origin backtest (24h hybrid, across winters)",
        "",
        "Expanding training window, frozen model architecture, test on each winter.",
        "Skill = 1 - metric_model / metric_persistence (positive = beats persistence).",
        "",
        "| Fold | Train n | Test n | Test source | Hybrid MAE | Persistence MAE | MAE skill | MAE-skill 95% CI | RMSE skill |",
        "| :--- | ---: | ---: | :--- | ---: | ---: | ---: | :---: | ---: |",
    ]
    for _, row in table.iterrows():
        lines.append(
            f"| {row.fold} | {row.n_train:,} | {row.n_test:,} | {row.aqi_source} | "
            f"{row.hybrid_mae} | {row.persistence_mae} | {row.skill_mae:+.4f} | "
            f"[{row.skill_mae_ci_lo:+.3f}, {row.skill_mae_ci_hi:+.3f}] | {row.skill_rmse:+.4f} |"
        )
    lines += [
        "",
        f"**Mean MAE skill across folds: {mean_mae:+.4f} ± {std_mae:.4f}**",
        "",
        f"**Mean RMSE skill across folds: {mean_rmse:+.4f} ± {std_rmse:.4f}**",
        "",
        "## Notes",
        "",
        "- The winter-2024 fold is scored against the CPCB-*recomputed* AQI (no",
        "  official label exists for 2024), so its absolute errors include the",
        "  reconstruction noise; the winter-2025 fold is scored against official AQI.",
        "- Training rows issued in the 24h before each test window are dropped (24h embargo),",
        "  because their t+24 labels fall inside the test window.",
        f"- CIs are 95% day-block bootstrap intervals within each fold ({N_BOOT:,} resamples, seed 42).",
        "- Only two folds are possible with the available labelled data (2024, 2025);",
        "  mean ± std over two folds is reported for completeness, not as a stable",
        "  estimate of variance.",
    ]
    (OUT_DIR / "rolling_origin_backtest.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_DIR / 'rolling_origin_backtest.md'}")


if __name__ == "__main__":
    main()

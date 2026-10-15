"""Parity of the served live products with the training path.

Same idea as ``src.live.parity`` (frozen models), for the products ``src.live.serving`` serves. History is cut from the
raw CSVs, QC'd and AQI-recomputed exactly as the live ingest does, reshaped like the database tables, and pushed through
the production functions (``to_inputs`` -> ``build_frames`` -> ``serving.predict`` / ``forecast.rule_value``). Predictions
only: no error against actuals is computed, so the test window is not re-scored.

  AQI 6h / 24h   against the predictions the retrain stored (``reports/modeling/live_retrain/predictions_*``), tolerance 1e-6
  PM2.5 1h / 6h  against the same model scored on the training matrix row (``data/processed/features_live_masked.parquet``,
                 built by ``python -m src.features.build_live_matrix``): the live-path feature row must give the same forecast
  AQI 1h rule    against the hourly-AQI frame the baseline evaluation used (``window_update_baseline``)

    python -m src.live.parity_live [--times 25] [--seed 0]      # writes docs/TIER_3/parity_live_report.{md,csv}

Needs ``Og Data/``; the PM2.5 check also needs the masked matrix. LightGBM and numpy 2 are needed to load the models.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.window_update_baseline import hourly_aqi_frame
from src.features.build_features import OFFLINE_END, OFFLINE_START, load_caaqms_offline
from src.features.build_live_matrix import PATHS, apply_mask, recomputed_aqi
from src.live import forecast, serving
from src.live.config import load_forecast_config
from src.live.forecast import KST
from src.live.parity import _features_with_training_rolling, sample_times
from src.live.qc import apply_qc

REPO_ROOT = Path(__file__).resolve().parents[2]
TOLERANCE = 1e-6
RETRAIN = "reports/modeling/live_retrain"
STORED = {
    "aqi_6h": [("val", f"{RETRAIN}/predictions_6h_val.parquet"), ("test", f"{RETRAIN}/predictions_6h_test.parquet")],
    "aqi_24h": [("val", f"{RETRAIN}/predictions_24h_val.parquet"), ("test", f"{RETRAIN}/predictions_24h_test.parquet")],
}


def load_history(mask: str = "none") -> tuple[pd.DataFrame, pd.DataFrame]:
    """QC'd, AQI-recomputed history reshaped like the DB tables (readings: station_id, ts, values; aqi: station_id, ts, aqi).
    ``mask='live'`` blanks the inputs the live sources do not provide, after the AQI is computed (as the ingest does)."""
    caaqms, _ = apply_qc(load_caaqms_offline(OFFLINE_START, OFFLINE_END))
    aqi = recomputed_aqi(caaqms)
    readings = (
        apply_mask(caaqms, mask)
        .rename(columns={"timestamp": "ts"})
        .drop(columns=["station_name", "no"], errors="ignore")
    )
    readings["qc_flags"] = [{} for _ in range(len(readings))]
    return readings, aqi.rename(columns={"timestamp": "ts", "aqi_value": "aqi"})[["station_id", "ts", "aqi"]]


def _featured(caaqms: pd.DataFrame, aqi_df: pd.DataFrame, t: pd.Timestamp, variant: str) -> pd.DataFrame:
    if variant == "live path":
        return forecast.build_frames(caaqms, aqi_df, t)[1]
    return _features_with_training_rolling(caaqms, aqi_df, t)


def compare_stored(
    models: serving.Serving,
    key: str,
    label: str,
    path: str,
    readings: pd.DataFrame,
    aqi: pd.DataFrame,
    n: int,
    seed: int,
) -> pd.DataFrame:
    stored = pd.read_parquet(REPO_ROOT / path)
    stored["timestamp"] = pd.to_datetime(stored["timestamp"]).dt.tz_convert(KST)
    caaqms, aqi_df = forecast.to_inputs(readings, aqi, weather_fill="none")
    parts = []
    for variant in ("live path", "rolling from training start"):
        for t in sample_times(stored, n, seed):
            at = _featured(caaqms, aqi_df, t, variant)
            at = (
                at[at["timestamp"] == t]
                .dropna(subset=["aqi_curr"])
                .merge(stored[stored["timestamp"] == t][["station_id", "prediction"]], on="station_id")
            )
            if at.empty:
                continue
            mine = serving.predict(models, key, at)
            parts.append(
                pd.DataFrame(
                    {
                        "product": key,
                        "reference": f"retrain predictions ({label})",
                        "variant": variant,
                        "issue_time": t,
                        "abs_diff": np.abs(mine - at["prediction"].to_numpy(float)),
                    }
                )
            )
    return pd.concat(parts, ignore_index=True)


def compare_matrix(
    models: serving.Serving,
    key: str,
    readings: pd.DataFrame,
    aqi: pd.DataFrame,
    matrix: pd.DataFrame,
    n: int,
    seed: int,
) -> pd.DataFrame:
    """Live-path feature row vs the training-matrix row at the same hour: same model, so the forecasts must agree."""
    caaqms, aqi_df = forecast.to_inputs(readings, aqi, weather_fill="none")
    hours = matrix[matrix["split"] == "val"]["timestamp"].drop_duplicates()
    parts = []
    for t in sorted(hours.sample(min(n, len(hours)), random_state=seed)):
        t = t.tz_localize(KST) if t.tzinfo is None else t.tz_convert(KST)
        for variant in ("live path", "rolling from training start"):
            at = _featured(caaqms, aqi_df, t, variant)
            at = at[at["timestamp"] == t].dropna(subset=["aqi_curr"])
            ref = matrix[matrix["timestamp"] == t].set_index("station_id")
            at = at[at["station_id"].isin(ref.index)]
            if at.empty:
                continue
            ref_rows = ref.loc[at["station_id"]].reset_index()
            ref_rows["station_name"] = at["station_name"].to_numpy()
            diff = np.abs(serving.predict(models, key, at) - serving.predict(models, key, ref_rows))
            parts.append(
                pd.DataFrame(
                    {
                        "product": key,
                        "reference": "training matrix row",
                        "variant": variant,
                        "issue_time": t,
                        "abs_diff": diff,
                    }
                )
            )
    return pd.concat(parts, ignore_index=True)


def compare_rule(readings: pd.DataFrame, aqi: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """``forecast.rule_value`` on DB-shaped history vs the baseline evaluation's hourly frame."""
    caaqms, _ = forecast.to_inputs(readings, aqi, weather_fill="none")
    reference = hourly_aqi_frame().dropna(subset=["wu_1h", "aqi_recomputed"])
    reference = reference[reference["timestamp"] >= pd.Timestamp("2025-11-01")]
    rng = np.random.default_rng(seed)
    picks = reference.iloc[rng.choice(len(reference), size=min(n * 7, len(reference)), replace=False)]
    names = {v: k for k, v in forecast.STATION_IDS.items()}
    rows = []
    for r in picks.itertuples():
        issue = pd.Timestamp(r.timestamp).tz_localize(KST)
        value, _ = forecast.rule_value(caaqms, names[r.station_id], issue, float(r.aqi_recomputed))
        rows.append(
            {
                "product": "aqi_1h",
                "reference": "baseline evaluation (window_update_baseline)",
                "variant": "live path",
                "issue_time": issue,
                "abs_diff": np.nan if value is None else abs(value - r.wu_1h),
            }
        )
    return pd.DataFrame(rows)


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    return (
        detail.groupby(["product", "reference", "variant"])
        .agg(
            issue_hours=("issue_time", "nunique"),
            rows=("abs_diff", "size"),
            compared=("abs_diff", "count"),
            max_abs_diff=("abs_diff", "max"),
            rows_over_tolerance=("abs_diff", lambda d: int((d > TOLERANCE).sum())),
        )
        .reset_index()
    )


def write_report(summary: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "parity_live_report.csv", index=False)
    lines = [
        "# Live products: parity with the training path",
        "",
        f"Tolerance {TOLERANCE:g} (absolute). Generated by `python -m src.live.parity_live`; numbers come from `parity_live_report.csv`.",
        "Predictions only, no error against actuals, so the test window is not re-scored. `live path` is what the hourly job does; "
        "`rolling from training start` starts the rolling windows where training's did (pandas rolling statistics differ in the last digits "
        "by where the window began, which can flip a tree split that sits exactly on a threshold).",
        "",
        "| Product | Reference | Features | Issue hours | Rows | Compared | Max abs diff | Rows over tolerance |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {r.product} | {r.reference} | {r.variant} | {r.issue_hours} | {r.rows} | {r.compared} | {r.max_abs_diff:.3g} | {r.rows_over_tolerance} |"
        for r in summary.itertuples()
    ]
    (out_dir / "parity_live_report.md").write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=25)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    models = serving.load(load_forecast_config())
    parts = []
    readings, aqi = load_history("none")
    for key, sets in STORED.items():
        for label, path in sets:
            parts.append(compare_stored(models, key, label, path, readings, aqi, args.times, args.seed))
    parts.append(compare_rule(readings, aqi, args.times, args.seed))
    matrix_path = PATHS["live"]
    if matrix_path.exists():
        matrix = pd.read_parquet(matrix_path)
        from src.models.splits import assign_split

        matrix["split"] = assign_split(matrix["timestamp"])
        readings_live, aqi_live = load_history("live")
        for key in ("pm25_1h", "pm25_6h"):
            parts.append(compare_matrix(models, key, readings_live, aqi_live, matrix, args.times, args.seed))
    else:
        print(f"{matrix_path} missing: PM2.5 parity skipped (python -m src.features.build_live_matrix builds it)")
    summary = summarize(pd.concat(parts, ignore_index=True))
    write_report(summary, REPO_ROOT / "docs" / "TIER_3")
    print(summary.to_string(index=False))
    exact = summary[summary["variant"] != "live path"]
    return 0 if (exact["rows_over_tolerance"] == 0).all() and (summary["compared"] > 0).all() else 1


if __name__ == "__main__":
    sys.exit(main())

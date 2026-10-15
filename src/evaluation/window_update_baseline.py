"""Window-update persistence: a stronger baseline than plain persistence for the live (recomputed) AQI.

The live AQI is a trailing 24h mean of an hourly AQI ``H``: AQI(t) = mean(H(t-23..t)). So

    AQI(t+h) = AQI(t) + sum_{k=1..h} (H(t+k) - H(t+k-24)) / 24

and every ``H(t+k-24)`` leaving the window is known at ``t``. The baseline assumes the unknown entering hours stay at the
current hourly value, ``H(t+k) = H(t)``, and recomputes the window mean exactly as ``compute_aqi`` does (same
``MIN_VALID_HOURS`` rule), so gaps are handled the same way. It has no fitted parameters.

This reads the saved retrain predictions (no model is refit and no test row is re-scored for selection), rebuilds ``H``
from the QC'd raw telemetry, and reports the retrained model against plain persistence and against this baseline, with
95% day-block bootstrap CIs. It also reports each model's gain-based feature importance from its LightGBM text dump.

    python -m src.evaluation.window_update_baseline
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.build_metrics_table import block_bootstrap
from src.features.build_features import OFFLINE_END, OFFLINE_START, load_caaqms_offline
from src.features.compute_cpcb_aqi import MIN_VALID_HOURS, POLLUTANTS, ROLLING_WINDOW_HOURS, hourly_aqi_series
from src.live.log import configure, get_logger
from src.live.qc import apply_qc
from src.live.rules import window_update_estimate

REPO_ROOT = Path(__file__).resolve().parents[2]
RETRAIN_DIR = REPO_ROOT / "reports" / "modeling" / "live_retrain"
MODEL_DIR = REPO_ROOT / "models" / "live"
N_BOOT, SEED = 1000, 42
HORIZONS = (1, 6, 24)
log = get_logger(__name__)


def hourly_aqi_frame() -> pd.DataFrame:
    """Hourly (un-averaged) live-basis AQI per station, built from the same QC'd telemetry the retrain matrix used."""
    caaqms, _ = apply_qc(load_caaqms_offline(OFFLINE_START, OFFLINE_END))
    raw = caaqms.drop_duplicates(["station_id", "timestamp"]).sort_values(["station_id", "timestamp"])
    frames = []
    for station_id, group in raw.groupby("station_id"):
        series = group.set_index("timestamp")[POLLUTANTS].sort_index()
        series = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="h"))
        hourly = hourly_aqi_series(series)
        frame = pd.DataFrame({"station_id": station_id, "timestamp": hourly.index, "hourly_aqi": hourly.to_numpy()})
        frame["aqi_recomputed"] = hourly.rolling(ROLLING_WINDOW_HOURS, min_periods=MIN_VALID_HOURS).mean().to_numpy()
        for horizon in HORIZONS:
            frame[f"wu_{horizon}h"] = window_update_estimate(hourly, horizon).to_numpy()
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    out["timestamp"] = _naive_local(out["timestamp"])
    return out


def _naive_local(stamps: pd.Series) -> pd.Series:
    stamps = pd.to_datetime(stamps)
    return stamps.dt.tz_localize(None) if stamps.dt.tz is not None else stamps


def _skill(y: np.ndarray, pred: np.ndarray, ref: np.ndarray, days: np.ndarray) -> tuple[float, float, float]:
    skill = 1.0 - np.abs(pred - y).mean() / np.abs(ref - y).mean()
    ci = block_bootstrap(y, pred, ref, days, N_BOOT, SEED)
    return float(skill), float(ci["skill_mae_ci_lo"]), float(ci["skill_mae_ci_hi"])


def evaluate(hourly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon in HORIZONS:
        for split in ("val", "test"):
            preds = pd.read_parquet(RETRAIN_DIR / f"predictions_{horizon}h_{split}.parquet")
            preds["_ts"] = _naive_local(preds["timestamp"])
            merged = preds.merge(
                hourly[["station_id", "timestamp", "aqi_recomputed", f"wu_{horizon}h"]].rename(
                    columns={"timestamp": "_ts"}
                ),
                on=["station_id", "_ts"],
                how="left",
            )
            drift = (merged["aqi_recomputed"] - merged["aqi_curr"]).abs().max()
            if not drift < 1e-6:
                raise SystemExit(f"{horizon}h {split}: rebuilt AQI(t) disagrees with the matrix (max diff {drift})")
            merged["wu"] = merged[f"wu_{horizon}h"]
            fallback = int(merged["wu"].isna().sum())
            merged["wu"] = merged["wu"].fillna(merged["aqi_curr"])  # current hour missing: plain persistence
            y = merged[f"target_aqi_{horizon}h"].to_numpy(float)
            persist = merged["aqi_curr"].to_numpy(float)
            model, base = merged["prediction"].to_numpy(float), merged["wu"].to_numpy(float)
            days = pd.to_datetime(merged["_ts"]).dt.date.values
            mae = {k: float(np.abs(v - y).mean()) for k, v in {"model": model, "wu": base, "persist": persist}.items()}
            m_p, m_lo, m_hi = _skill(y, model, persist, days)
            b_p, b_lo, b_hi = _skill(y, base, persist, days)
            m_b, mb_lo, mb_hi = _skill(y, model, base, days)
            gap = mae["persist"] - mae["model"]
            rows.append(
                {
                    "horizon": f"{horizon}h",
                    "split": split,
                    "n": len(merged),
                    "wu_fallback_rows": fallback,
                    "persistence_mae": mae["persist"],
                    "window_update_mae": mae["wu"],
                    "model_mae": mae["model"],
                    "wu_vs_persistence": b_p,
                    "wu_vs_persistence_lo": b_lo,
                    "wu_vs_persistence_hi": b_hi,
                    "model_vs_persistence": m_p,
                    "model_vs_persistence_lo": m_lo,
                    "model_vs_persistence_hi": m_hi,
                    "model_vs_window_update": m_b,
                    "model_vs_window_update_lo": mb_lo,
                    "model_vs_window_update_hi": mb_hi,
                    "share_of_gain_from_window_update": (mae["persist"] - mae["wu"]) / gap if gap > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def gain_importance(model_text: str) -> pd.Series:
    """Total split gain per feature, normalised to sum to 1, from a LightGBM text dump."""
    names = re.search(r"^feature_names=(.*)$", model_text, re.M).group(1).split()
    gain: collections.Counter = collections.Counter()
    features = re.findall(r"^split_feature=(.*)$", model_text, re.M)
    gains = re.findall(r"^split_gain=(.*)$", model_text, re.M)
    for tree_features, tree_gains in zip(features, gains, strict=True):
        for index, value in zip(tree_features.split(), tree_gains.split(), strict=True):
            gain[names[int(index)]] += float(value)
    total = sum(gain.values())
    return pd.Series({name: value / total for name, value in gain.most_common()})


def feature_family(name: str) -> str:
    if name == "aqi_curr":
        return "aqi_curr"
    if name.startswith("aqi_") or "_aqi_" in name:
        return "AQI history (lags, rolling, network)"
    if name.startswith(("pm25", "pm10")):
        return "PM history"
    return "everything else"


def importance_table() -> pd.DataFrame:
    rows = []
    for horizon in (1, 6):
        gain = gain_importance((MODEL_DIR / f"aqi-{horizon}h-lgb-live-v1.txt").read_text())
        for name, share in gain.head(8).items():
            rows.append({"horizon": f"{horizon}h", "feature": name, "gain_share": share})
        for family, share in gain.groupby(gain.index.map(feature_family)).sum().sort_values(ascending=False).items():
            rows.append({"horizon": f"{horizon}h", "feature": f"[family] {family}", "gain_share": share})
    return pd.DataFrame(rows)


def main() -> int:
    configure()
    results = evaluate(hourly_aqi_frame())
    importance = importance_table()
    results.to_csv(RETRAIN_DIR / "window_update_baseline.csv", index=False)
    importance.to_csv(RETRAIN_DIR / "feature_importance_gain.csv", index=False)
    log.info("wrote window_update_baseline.csv and feature_importance_gain.csv to %s", RETRAIN_DIR)
    print(results.round(4).to_string(index=False))
    print(importance.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

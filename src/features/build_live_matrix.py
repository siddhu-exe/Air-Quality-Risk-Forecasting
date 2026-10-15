"""Live-consistent feature matrix: the AQI definition the live pipeline serves, used for training too.

The live ingest recomputes AQI from QC'd hourly pollutants (``compute_aqi``, method ``rolling_subindex_mean``). The frozen
models were trained on the official AQI for 2025, which sits on average ~5.5 points higher (WAQI audit,
reports/modeling/live_audit/waqi_roundtrip_audit.md), so serving them recomputed AQI collapses their 1h/6h skill. This
module rebuilds the 2024-2025 matrix with the SAME definition for the input features (``aqi_curr``, AQI lags and rolling
statistics, cross-station AQI) and for the targets, through the shared ``compute_feature_frame`` (no second feature path).

Steps: raw CSVs -> cell-level QC (``src/live/qc.py``, as the backfill and the live ingest) -> ``compute_aqi`` on the cleaned
pollutants -> features. ``mask='live'`` then blanks the inputs the live sources do not provide (NOx/NO everywhere, solar
radiation everywhere, ITO temperature/humidity/wind) AFTER the AQI is computed, which is what the ingest does (AQI never
used those columns).

    python -m src.features.build_live_matrix                     # writes both matrices to data/processed/
    python -m src.features.build_live_matrix --start 2025-07-01 --out-dir /tmp/x   # short window, code-path check
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.build_features import (
    OFFLINE_END,
    OFFLINE_START,
    _stations_frame,
    compute_feature_frame,
    load_caaqms_offline,
)
from src.features.compute_cpcb_aqi import POLLUTANTS, compute_aqi
from src.live.qc import apply_qc

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"
PATHS = {"none": PROCESSED / "features_live.parquet", "live": PROCESSED / "features_live_masked.parquet"}
MASKED_EVERYWHERE = ["nox", "no", "solar_radiation"]
MASKED_AT = {"ITO": ["temperature", "humidity", "wind_speed"]}


def recomputed_aqi(caaqms: pd.DataFrame) -> pd.DataFrame:
    """AQI from the (already QC'd) hourly pollutants, exactly as ``src.live.ingest.recompute_aqi`` does."""
    raw = caaqms.drop_duplicates(["station_id", "timestamp"]).rename(columns={"timestamp": "Timestamp"})
    raw = raw[["station_id", "station_name", "Timestamp", *POLLUTANTS]].sort_values(["station_id", "Timestamp"])
    return compute_aqi(raw).dropna(subset=["aqi_value"]).assign(aqi_source="recomputed")


def apply_mask(caaqms: pd.DataFrame, mask: str) -> pd.DataFrame:
    if mask == "none":
        return caaqms
    if mask != "live":
        raise ValueError(f"mask must be 'none' or 'live', got {mask!r}")
    out = caaqms.copy()
    out[MASKED_EVERYWHERE] = np.nan
    for station, columns in MASKED_AT.items():
        out.loc[out.station_name == station, columns] = np.nan
    return out


def _kolkata(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("Asia/Kolkata") if stamp.tzinfo is None else stamp.tz_convert("Asia/Kolkata")


def build(mask: str = "none", start=None, end=None) -> pd.DataFrame:
    start = _kolkata(start) if start is not None else OFFLINE_START
    end = _kolkata(end) if end is not None else OFFLINE_END
    caaqms, _ = apply_qc(load_caaqms_offline(start, end))
    aqi = recomputed_aqi(caaqms)
    return compute_feature_frame(_stations_frame(), apply_mask(caaqms, mask), aqi, start, end, start, end)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--start", help="first hour (default 2024-01-01); a shorter window is for code-path checks only"
    )
    parser.add_argument("--end", help="last hour (default 2025-12-31 23:00)")
    parser.add_argument(
        "--out-dir", type=Path, default=PROCESSED, help="where features_live[_masked].parquet are written"
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for mask, path in PATHS.items():
        target = args.out_dir / path.name
        frame = build(mask, args.start, args.end)
        frame.to_parquet(target, index=False)
        print(f"wrote {target} {frame.shape} {frame.timestamp.min()} .. {frame.timestamp.max()}")


if __name__ == "__main__":
    main()

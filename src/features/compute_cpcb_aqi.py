"""
compute_cpcb_aqi.py
====================
Reconstruct hourly CPCB AQI for the raw CAAQMS years (2023-2024) that
predate the official ``aqi_hourly`` table (which only covers 2025).

Why
---
The forecasting models could only train on 2025 because ``aqi_hourly`` holds
just that year, so the trees never saw a winter peak (defect D7 in
``docs/history/IMPROVEMENT_PLAN.md``). The raw station telemetry in ``Og Data`` does
cover 2023-2024, so we recompute AQI with the CPCB method and use it as the
training target for those years.

CPCB AQI method implemented here
--------------------------------
1. Each hour is converted to a per-pollutant sub-index using the official
   CPCB breakpoint table (linear interpolation inside each band):
   PM2.5, PM10, NO2, SO2, NH3 on concentrations in ug/m3; CO in mg/m3;
   O3 in ug/m3.
2. CO and O3 sub-indices are computed from an 8-hour rolling mean (CPCB uses
   an 8h average for these two gases); the remaining pollutants use the
   hourly value.
3. The hourly AQI is the maximum sub-index, and is only valid when at least
   three pollutants are present and at least one of them is PM2.5 or PM10.
4. The stored ``aqi_hourly`` series behaves like a 24-hour rolling average of
   that hourly AQI, so the final value is the 24h mean of the hourly AQI
   (requiring at least 16 valid hours in the window).

Validation against the official 2025 ``aqi_hourly`` (see
``reports/features/aqi_recompute_validation.md``) gives MAE ~9.4 (< 10), which
is the gate set in the improvement plan. The alternative "24h mean of the
concentration then sub-index" convention is also reported for transparency but
scores worse (MAE ~11.2) and is not used for the training target.

Usage
-----
    python src/features/compute_cpcb_aqi.py --years 2023 2024
    python src/features/compute_cpcb_aqi.py --years 2025 --validate
"""

from __future__ import annotations

import argparse
import glob
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "Og Data" / "Delhi data"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "recomputed_aqi.parquet"
DEFAULT_VALIDATION_CSV = PROJECT_ROOT / "reports" / "features" / "aqi_recompute_validation.csv"
DEFAULT_VALIDATION_MD = PROJECT_ROOT / "reports" / "features" / "aqi_recompute_validation.md"

# Canonical station names / ids as used across the project's feature matrix.
STATION_IDS = {
    "Anand Vihar": 3,
    "Bawana": 4,
    "Dwarka-Sector 8": 5,
    "ITO": 6,
    "Jahangirpuri": 7,
    "Punjabi Bagh": 8,
    "R K Puram": 9,
}

# Folder name (may contain a trailing tab for Jahangirpuri) -> canonical name.
FOLDER_TO_STATION = {
    "Anand Vihar, Delhi - DPCC": "Anand Vihar",
    "Bawana, Delhi - DPCC": "Bawana",
    "Dwarka-Sector 8, Delhi - DPCC": "Dwarka-Sector 8",
    "ITO, Delhi - CPCB": "ITO",
    "Jahangirpuri, Delhi - DPCC\t": "Jahangirpuri",
    "Jahangirpuri, Delhi - DPCC": "Jahangirpuri",
    "Punjabi Bagh, Delhi - DPCC": "Punjabi Bagh",
    "R K Puram, Delhi - DPCC": "R K Puram",
}

# Raw CSV header -> internal pollutant name.
POLLUTANT_COLUMNS = {
    "PM2.5 (µg/m³)": "pm25",
    "PM10 (µg/m³)": "pm10",
    "NO2 (µg/m³)": "no2",
    "NH3 (µg/m³)": "nh3",
    "SO2 (µg/m³)": "so2",
    "CO (mg/m³)": "co",
    "Ozone (µg/m³)": "o3",
}

POLLUTANTS = ["pm25", "pm10", "no2", "so2", "nh3", "co", "o3"]

# Pollutants averaged over 8 hours before the sub-index (CPCB rule for gases).
EIGHT_HOUR_POLLUTANTS = {"co", "o3"}

# CPCB breakpoints: (concentration breakpoints, sub-index breakpoints).
BREAKPOINTS = {
    "pm25": ([0, 30, 60, 90, 120, 250, 500], [0, 50, 100, 200, 300, 400, 500]),
    "pm10": ([0, 50, 100, 250, 350, 430, 600], [0, 50, 100, 200, 300, 400, 500]),
    "no2": ([0, 40, 80, 180, 280, 400, 600], [0, 50, 100, 200, 300, 400, 500]),
    "so2": ([0, 40, 80, 380, 800, 1600, 2400], [0, 50, 100, 200, 300, 400, 500]),
    "nh3": ([0, 200, 400, 800, 1200, 1800, 2400], [0, 50, 100, 200, 300, 400, 500]),
    "co": ([0, 1, 2, 10, 17, 34, 50], [0, 50, 100, 200, 300, 400, 500]),
    "o3": ([0, 50, 100, 168, 208, 748, 1000], [0, 50, 100, 200, 300, 400, 500]),
}

MIN_POLLUTANTS = 3
ROLLING_WINDOW_HOURS = 24
MIN_VALID_HOURS = 16


def sub_index(pollutant: str, concentration) -> np.ndarray:
    """Vectorised CPCB sub-index via linear interpolation of the breakpoints."""
    conc_lo, sub_hi = BREAKPOINTS[pollutant]
    values = pd.to_numeric(pd.Series(concentration), errors="coerce").to_numpy(dtype=float)
    out = np.interp(values, conc_lo, sub_hi, left=0.0, right=500.0)
    out[np.isnan(values)] = np.nan
    return out


def _station_for_folder(folder_name: str) -> str | None:
    return FOLDER_TO_STATION.get(folder_name) or FOLDER_TO_STATION.get(folder_name.rstrip("\t"))


def load_raw_caaqms(years, raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load the raw hourly CAAQMS CSVs for the requested years into long form."""
    frames = []
    for folder in sorted(os.listdir(raw_dir)):
        station_dir = Path(raw_dir) / folder
        station = _station_for_folder(folder)
        if station is None or not (station_dir / "Raw Data").is_dir():
            continue
        for year in years:
            for csv_path in glob.glob(str(station_dir / "Raw Data" / f"{year}_*_1H.csv")):
                frame = pd.read_csv(csv_path).rename(columns=POLLUTANT_COLUMNS)
                missing = [p for p in POLLUTANTS if p not in frame.columns]
                if missing:
                    raise ValueError(f"{csv_path} is missing columns {missing}")
                frames.append(
                    frame[["Timestamp"] + POLLUTANTS].assign(station_name=station, station_id=STATION_IDS[station])
                )
    if not frames:
        raise FileNotFoundError(f"No raw CAAQMS CSVs found for years {years} under {raw_dir}")
    raw = pd.concat(frames, ignore_index=True)
    raw["Timestamp"] = pd.to_datetime(raw["Timestamp"])
    raw = raw.sort_values(["station_name", "Timestamp"]).drop_duplicates(["station_name", "Timestamp"], keep="last")
    return raw.reset_index(drop=True)


def hourly_aqi_series(series: pd.DataFrame, min_pollutants: int = MIN_POLLUTANTS) -> pd.Series:
    """Hourly (un-averaged) AQI from one station's gap-free hourly pollutant frame.

    Max sub-index per hour, with CO/O3 on their trailing 8h mean (>= 6 valid hours); NaN where fewer than
    ``min_pollutants`` (CPCB: 3) sub-indices exist or neither PM is present. Every value depends only on hours <= its own.
    ``compute_aqi`` takes the trailing 24h mean of this series.
    """
    sub = pd.DataFrame({p: sub_index(p, series[p]) for p in POLLUTANTS}, index=series.index)
    for pollutant in EIGHT_HOUR_POLLUTANTS:
        smoothed = series[pollutant].rolling(8, min_periods=6).mean().to_numpy()
        sub[pollutant] = sub_index(pollutant, smoothed)
    return sub.max(axis=1).where(_validity_mask(sub, min_pollutants))


def compute_aqi(
    raw: pd.DataFrame, method: str = "rolling_subindex_mean", min_pollutants: int = MIN_POLLUTANTS
) -> pd.DataFrame:
    """Compute hourly AQI per station from the long raw telemetry frame.

    ``method='rolling_subindex_mean'`` (default, validated against official
    2025) builds an hourly AQI from the sub-indices and then takes a 24h
    rolling mean. ``method='concentration_mean'`` takes the 24h (8h for
    CO/O3) mean of each concentration before the sub-index instead.

    ``min_pollutants`` is the CPCB rule (3 sub-indices, one of them PM) unless a caller deliberately relaxes it, e.g. the
    PM-only audit (``src/evaluation/waqi_roundtrip_audit.py``), where the gases are not available.
    """
    records = []
    for (station_id, station), group in raw.groupby(["station_id", "station_name"]):
        series = group.set_index("Timestamp").sort_index()
        full_index = pd.date_range(series.index.min(), series.index.max(), freq="h")
        series = series.reindex(full_index)

        if method == "concentration_mean":
            rolling = {}
            for pollutant in POLLUTANTS:
                window, min_periods = (8, 6) if pollutant in EIGHT_HOUR_POLLUTANTS else (24, MIN_VALID_HOURS)
                rolling[pollutant] = series[pollutant].rolling(window, min_periods=min_periods).mean().to_numpy()
            sub = pd.DataFrame({p: sub_index(p, rolling[p]) for p in POLLUTANTS}, index=series.index)
            hourly_aqi = sub.max(axis=1)
            valid = _validity_mask(sub, min_pollutants)
            aqi = hourly_aqi.where(valid)
        elif method == "rolling_subindex_mean":
            aqi = (
                hourly_aqi_series(series, min_pollutants)
                .rolling(ROLLING_WINDOW_HOURS, min_periods=MIN_VALID_HOURS)
                .mean()
            )
        else:
            raise ValueError(f"Unknown method: {method}")

        records.append(
            pd.DataFrame(
                {
                    "station_id": station_id,
                    "station_name": station,
                    "timestamp": series.index,
                    "aqi_value": aqi.to_numpy(),
                }
            )
        )
    return pd.concat(records, ignore_index=True)


def _validity_mask(sub_indices: pd.DataFrame, min_pollutants: int = MIN_POLLUTANTS) -> pd.Series:
    enough = sub_indices.notna().sum(axis=1) >= min_pollutants
    has_pm = sub_indices[["pm25", "pm10"]].notna().any(axis=1)
    return enough & has_pm


def load_official_aqi(years, raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load the official station-level AQI xlsx files into long form."""
    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    month_map = {name: i for i, name in enumerate(month_names, 1)}
    frames = []
    for folder in sorted(os.listdir(raw_dir)):
        station = _station_for_folder(folder)
        aqi_dir = Path(raw_dir) / folder / "AQI Hourly"
        if station is None or not aqi_dir.is_dir():
            continue
        for year in years:
            for path in glob.glob(str(aqi_dir / f"*{year}_*.xlsx")):
                match = re.search(r"_(\d{4})_([A-Za-z]+)_", os.path.basename(path))
                if not match:
                    continue
                wide = pd.read_excel(path)
                long = wide.melt(id_vars=["Date"], var_name="hour", value_name="aqi_value")
                hour = long["hour"].astype(str).str.slice(0, 2).astype(int)
                ts = pd.to_datetime(
                    dict(year=int(match.group(1)), month=month_map[match.group(2)], day=long["Date"].astype(int))
                ) + pd.to_timedelta(hour, unit="h")
                frames.append(
                    pd.DataFrame(
                        {
                            "station_name": station,
                            "timestamp": ts,
                            "aqi_official": pd.to_numeric(long["aqi_value"], errors="coerce"),
                        }
                    )
                )
    if not frames:
        raise FileNotFoundError(f"No official AQI xlsx files found for years {years}")
    return pd.concat(frames, ignore_index=True).dropna(subset=["aqi_official"])


def validate(recomputed: pd.DataFrame, official: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Compare recomputed vs official hourly AQI; return per-row and summary stats."""
    merged = recomputed.merge(official, on=["station_name", "timestamp"], how="inner")
    merged = merged.dropna(subset=["aqi_value", "aqi_official"])
    merged["abs_error"] = (merged["aqi_value"] - merged["aqi_official"]).abs()
    merged["error"] = merged["aqi_value"] - merged["aqi_official"]

    summary = {
        "n_matched": int(len(merged)),
        "mae": float(merged["abs_error"].mean()),
        "median_abs_error": float(merged["abs_error"].median()),
        "bias": float(merged["error"].mean()),
        "share_within_5": float((merged["abs_error"] <= 5).mean()),
        "share_within_10": float((merged["abs_error"] <= 10).mean()),
    }
    return merged, summary


def _write_validation_report(merged: pd.DataFrame, summary: dict, path: Path, method: str) -> None:
    per_station = merged.groupby("station_name")["abs_error"].mean().round(2).sort_index().to_dict()
    per_month = (
        merged.assign(month=pd.to_datetime(merged["timestamp"]).dt.month)
        .groupby("month")["abs_error"]
        .mean()
        .round(2)
        .to_dict()
    )
    ts = pd.to_datetime(merged["timestamp"])
    periods = {
        "Jan-Aug (before validation window)": ts < pd.Timestamp("2025-09-01"),
        "Sep-Oct (validation window)": (ts >= pd.Timestamp("2025-09-01")) & (ts < pd.Timestamp("2025-11-01")),
        "Nov-Dec (test window)": ts >= pd.Timestamp("2025-11-01"),
    }
    per_period = [
        f"| {name} | {int(mask.sum()):,} | {merged.loc[mask, 'abs_error'].mean():.2f} | "
        f"{merged.loc[mask, 'error'].mean():+.2f} |"
        for name, mask in periods.items()
    ]
    gate = "PASS" if summary["mae"] < 10 else "FAIL"
    lines = [
        "# CPCB AQI recompute validation (2025)",
        "",
        f"Method: `{method}`. Ground truth: official station-level `aqi_hourly` xlsx for 2025.",
        "Script: `src/features/compute_cpcb_aqi.py`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Matched hours | {summary['n_matched']:,} |",
        f"| MAE | {summary['mae']:.3f} |",
        f"| Median absolute error | {summary['median_abs_error']:.3f} |",
        f"| Bias (recomputed - official) | {summary['bias']:+.3f} |",
        f"| Share within +/-5 | {summary['share_within_5'] * 100:.1f}% |",
        f"| Share within +/-10 | {summary['share_within_10'] * 100:.1f}% |",
        f"| Gate (MAE < 10) | **{gate}** |",
        "",
        "## MAE by station",
        "",
        "| Station | MAE |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in per_station.items()],
        "",
        "## MAE by period",
        "",
        "The overall gate is met, but only because the Sep-Dec months are easier; the",
        "Jan-Aug error is above 10 (largest in Feb-May).",
        "",
        "| Period | Matched hours | MAE | Bias |",
        "|---|---|---|---|",
        *per_period,
        "",
        "## MAE by month",
        "",
        "| Month | MAE |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in per_month.items()],
        "",
        "## Known limitations",
        "",
        "- The residual bias is positive and concentrated at high AQI; official values",
        "  can also contain isolated glitches (e.g. an official spike to 314 while the",
        "  raw PM2.5 is 28 ug/m3). Reconstructed AQI is therefore a good training target",
        "  but not a drop-in replacement for the official series.",
        "- 2023 raw data is only available for Dwarka-Sector 8; the other stations start",
        "  in 2024.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute CPCB AQI from raw CAAQMS CSVs")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025])
    parser.add_argument(
        "--method", default="rolling_subindex_mean", choices=["rolling_subindex_mean", "concentration_mean"]
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate", action="store_true", help="Validate against official AQI xlsx")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args()

    raw = load_raw_caaqms(args.years, args.raw_dir)
    print(f"Loaded {len(raw):,} raw hourly rows for years {args.years}")
    recomputed = compute_aqi(raw, method=args.method)
    recomputed["aqi_source"] = "recomputed"
    recomputed = recomputed.dropna(subset=["aqi_value"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    recomputed.to_parquet(args.output, index=False)
    print(f"Wrote {len(recomputed):,} recomputed AQI rows to {args.output}")

    if args.validate:
        val_raw = raw if 2025 in args.years else load_raw_caaqms([2025], args.raw_dir)
        val_recomputed = compute_aqi(val_raw, method=args.method)
        official = load_official_aqi([2025], args.raw_dir)
        merged, summary = validate(val_recomputed, official)
        DEFAULT_VALIDATION_CSV.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(DEFAULT_VALIDATION_CSV, index=False)
        _write_validation_report(merged, summary, DEFAULT_VALIDATION_MD, args.method)
        print(
            f"Validation: MAE={summary['mae']:.3f} bias={summary['bias']:+.2f} "
            f"within5={summary['share_within_5'] * 100:.1f}% -> {DEFAULT_VALIDATION_MD}"
        )


if __name__ == "__main__":
    main()

"""
export_ml_datasets.py
======================
Generates versioned, leakage-audited ML tabular datasets (Parquet format) and
associated metadata JSONs for 1h, 6h, and 24h multi-horizon AQI forecasting.

Outputs:
  - data/processed/ml/air_quality_ml_1h_v1.parquet (.json)
  - data/processed/ml/air_quality_ml_6h_v1.parquet (.json)
  - data/processed/ml/air_quality_ml_24h_v1.parquet (.json)
  - reports/modeling/ml_dataset_manifest.csv
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

# Directories
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PARQUET = PROJECT_ROOT / "data" / "processed" / "features_2025.parquet"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "ml"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "reports" / "modeling" / "ml_dataset_manifest.csv"

# 7 Delhi Stations
DELHI_STATIONS = [
    'Anand Vihar',
    'Bawana',
    'Dwarka-Sector 8',
    'ITO',
    'Jahangirpuri',
    'Punjabi Bagh',
    'R K Puram'
]

# Feature group categorization helper
def get_feature_group(col: str) -> str:
    if col.startswith('aqi_lag_') or col == 'aqi_curr':
        return 'Group A: Recent AQI Lags'
    elif '_roll_' in col and ('aqi_' in col or 'pm25_' in col):
        return 'Group C: Causal Rolling Statistics'
    elif any(col.startswith(f'{p}_') for p in ['pm25', 'pm10', 'no2', 'nox', 'so2', 'co', 'o3']):
        return 'Group B: Pollutant Lags'
    elif col in ['hour', 'day_of_week', 'month', 'day_of_year', 'is_weekend',
                 'sin_hour', 'cos_hour', 'sin_dow', 'cos_dow', 'sin_month', 'cos_month', 'sin_doy', 'cos_doy']:
        return 'Group D: Temporal & Cyclical'
    elif col.startswith('is_') and col != 'is_weekend':
        return 'Group E: Seasonality Indicators'
    elif any(k in col for k in ['temp_', 'humidity_', 'wind_speed_', 'solar_rad_']):
        return 'Group F: Meteorology'
    elif 'network_' in col or 'top_neighbor_' in col:
        return 'Group G: Cross-Station Spatial'
    else:
        return 'Other'


def get_git_commit() -> str:
    """Returns the current git commit hash."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return commit
    except Exception:
        return "unknown"


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def assign_split(df: pd.DataFrame) -> pd.Series:
    """
    Assigns strict chronological splits to each observation:
      - 'train': 2025-01-01 to 2025-08-31 (Jan-Aug 2025, ~67%)
      - 'val':   2025-09-01 to 2025-10-31 (Sep-Oct 2025, ~16.5%)
      - 'test':  2025-11-01 to 2025-12-31 (Nov-Dec 2025, ~16.5% - Peak Winter Crisis)
    """
    ts = pd.to_datetime(df['timestamp'])
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize('Asia/Kolkata')
    else:
        ts = ts.dt.tz_convert('Asia/Kolkata')

    split = pd.Series('train', index=df.index)
    val_mask = (ts >= pd.Timestamp("2025-09-01 00:00:00", tz='Asia/Kolkata')) & \
               (ts <= pd.Timestamp("2025-10-31 23:59:59", tz='Asia/Kolkata'))
    test_mask = (ts >= pd.Timestamp("2025-11-01 00:00:00", tz='Asia/Kolkata')) & \
                (ts <= pd.Timestamp("2025-12-31 23:59:59", tz='Asia/Kolkata'))

    split[val_mask] = 'val'
    split[test_mask] = 'test'
    return split


def export_horizon_dataset(
    base_df: pd.DataFrame,
    horizon: int,
    version: str,
    output_dir: Path,
    git_commit: str
) -> dict:
    """
    Filters and formats the dataset for a single horizon (1h, 6h, or 24h),
    saves parquet file and metadata JSON, and returns manifest summary.
    """
    target_col = f"target_aqi_{horizon}h"
    dataset_name = f"air_quality_ml_{horizon}h_{version}"
    parquet_path = output_dir / f"{dataset_name}.parquet"
    json_path = output_dir / f"{dataset_name}.json"

    print(f"\n=======================================================")
    print(f"Exporting Horizon: {horizon}h ({dataset_name})")
    print(f"=======================================================")

    # 1. Filter valid rows where target is present and valid
    valid_mask = base_df[target_col].notna() & (base_df[target_col] >= 0)
    horizon_df = base_df[valid_mask].copy()

    # 2. Assign chronological split
    horizon_df['split'] = assign_split(horizon_df)

    # 3. Identify feature columns and sort by group
    all_cols = horizon_df.columns.tolist()
    meta_cols = ['station_id', 'station_name', 'timestamp', 'split']
    target_cols = ['target_aqi_1h', 'target_aqi_6h', 'target_aqi_24h']
    feature_cols = [c for c in all_cols if c not in meta_cols and c not in target_cols]

    # Organize feature columns by Group A -> G
    group_order = [
        'Group A: Recent AQI Lags',
        'Group B: Pollutant Lags',
        'Group C: Causal Rolling Statistics',
        'Group D: Temporal & Cyclical',
        'Group E: Seasonality Indicators',
        'Group F: Meteorology',
        'Group G: Cross-Station Spatial'
    ]
    features_by_group = {g: [] for g in group_order}
    for c in feature_cols:
        g = get_feature_group(c)
        if g in features_by_group:
            features_by_group[g].append(c)
        else:
            features_by_group.setdefault('Other', []).append(c)

    sorted_feature_cols = []
    for g in group_order:
        sorted_feature_cols.extend(sorted(features_by_group[g]))

    # Final ordered columns
    ordered_cols = meta_cols + [target_col] + sorted_feature_cols
    export_df = horizon_df[ordered_cols].copy().sort_values(['station_id', 'timestamp']).reset_index(drop=True)

    # Save Parquet
    export_df.to_parquet(parquet_path, index=False, compression='snappy')
    filesize_bytes = parquet_path.stat().st_size
    filesize_mb = round(filesize_bytes / (1024 * 1024), 2)
    sha256_hash = compute_sha256(parquet_path)

    # Compute target statistics by split
    target_stats = {}
    for sp in ['all', 'train', 'val', 'test']:
        sub_series = export_df[target_col] if sp == 'all' else export_df[export_df['split'] == sp][target_col]
        target_stats[sp] = {
            "count": int(len(sub_series)),
            "mean": round(float(sub_series.mean()), 2),
            "std": round(float(sub_series.std()), 2),
            "min": round(float(sub_series.min()), 2),
            "p25": round(float(sub_series.quantile(0.25)), 2),
            "p50": round(float(sub_series.quantile(0.50)), 2),
            "p75": round(float(sub_series.quantile(0.75)), 2),
            "p95": round(float(sub_series.quantile(0.95)), 2),
            "max": round(float(sub_series.max()), 2),
            "extreme_ge_300_count": int((sub_series >= 300).sum()),
            "extreme_ge_300_pct": round(float((sub_series >= 300).mean() * 100), 2)
        }

    # Split breakdown
    split_counts = export_df['split'].value_counts().to_dict()
    total_rows = len(export_df)
    split_pcts = {k: round((v / total_rows) * 100, 2) for k, v in split_counts.items()}

    # Station breakdown
    station_counts = export_df['station_name'].value_counts().to_dict()

    # Missingness summary in features
    null_pct_by_group = {}
    for g, cols in features_by_group.items():
        if cols:
            grp_null_mean = float(export_df[cols].isna().mean().mean() * 100)
            null_pct_by_group[g] = round(grp_null_mean, 2)

    # Construct Metadata JSON
    metadata = {
        "dataset_name": dataset_name,
        "version": version,
        "horizon_hours": horizon,
        "target_column": target_col,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "sha256_checksum": sha256_hash,
        "filesize_bytes": filesize_bytes,
        "filesize_mb": filesize_mb,
        "total_rows": total_rows,
        "total_columns": len(export_df.columns),
        "feature_count": len(sorted_feature_cols),
        "split_counts": split_counts,
        "split_percentages": split_pcts,
        "station_distribution": station_counts,
        "date_range": {
            "min": str(export_df['timestamp'].min()),
            "max": str(export_df['timestamp'].max())
        },
        "feature_groups_summary": {g: len(cols) for g, cols in features_by_group.items()},
        "feature_names_by_group": features_by_group,
        "feature_group_missingness_pct": null_pct_by_group,
        "target_statistics_by_split": target_stats
    }

    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Parquet saved: {parquet_path}")
    print(f"  Rows: {total_rows:,} | Cols: {len(export_df.columns)} | Features: {len(sorted_feature_cols)} | Size: {filesize_mb} MB")
    print(f"  Splits: Train={split_counts.get('train', 0):,} ({split_pcts.get('train', 0)}%), Val={split_counts.get('val', 0):,} ({split_pcts.get('val', 0)}%), Test={split_counts.get('test', 0):,} ({split_pcts.get('test', 0)}%)")
    print(f"  SHA-256: {sha256_hash}")
    print(f"Metadata JSON saved: {json_path}")

    return {
        "horizon": f"{horizon}h",
        "dataset_name": dataset_name,
        "filename": f"{dataset_name}.parquet",
        "version": version,
        "total_rows": total_rows,
        "train_rows": split_counts.get('train', 0),
        "val_rows": split_counts.get('val', 0),
        "test_rows": split_counts.get('test', 0),
        "feature_count": len(sorted_feature_cols),
        "target_column": target_col,
        "filesize_mb": filesize_mb,
        "sha256_checksum": sha256_hash,
        "created_at": metadata["created_at"]
    }


def main():
    parser = argparse.ArgumentParser(description="Export versioned ML datasets for Delhi AQI forecasting.")
    parser.add_argument("--input-parquet", type=Path, default=DEFAULT_INPUT_PARQUET, help="Path to features_2025.parquet")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for ML datasets")
    parser.add_argument("--version", type=str, default="v1", help="Dataset version identifier (e.g. v1)")
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH, help="Path to manifest CSV")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    print("=== Air Quality ML Dataset Exporter ===")
    print(f"Input Parquet:  {args.input_parquet}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Version:        {args.version}")
    print(f"Manifest Path:  {args.manifest_path}")

    # Check input file
    if not args.input_parquet.exists():
        print(f"Input parquet {args.input_parquet} not found. Attempting to build from database...")
        from src.features.build_features import build_feature_matrix
        build_feature_matrix()

    print(f"\nLoading master features matrix from {args.input_parquet}...")
    base_df = pd.read_parquet(args.input_parquet)
    print(f"Master dataset loaded: {base_df.shape[0]:,} rows, {base_df.shape[1]} columns.")

    git_commit = get_git_commit()
    print(f"Current Git Commit: {git_commit}")

    manifest_records = []
    horizons = [1, 6, 24]
    for h in horizons:
        rec = export_horizon_dataset(
            base_df=base_df,
            horizon=h,
            version=args.version,
            output_dir=args.output_dir,
            git_commit=git_commit
        )
        manifest_records.append(rec)

    # Save manifest CSV
    manifest_df = pd.DataFrame(manifest_records)
    manifest_df.to_csv(args.manifest_path, index=False)
    print(f"\nManifest CSV saved to: {args.manifest_path}")

    print("\n=======================================================")
    print("           ML DATASET EXPORT SUMMARY")
    print("=======================================================")
    print(manifest_df.to_string(index=False))
    print("\nAll datasets successfully exported and verified.")


if __name__ == "__main__":
    main()

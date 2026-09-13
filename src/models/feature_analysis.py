"""
feature_analysis.py
Computes feature-to-target correlations, group-level importance distributions,
and exports feature ranking and baseline reports.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_PATH = Path("data/processed/features_2025.parquet")
REPORTS_DIR = Path("reports/modeling")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_feature_group(col):
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
    elif col == 'station_id':
        return 'Station Metadata'
    else:
        return 'Other'


def analyze_features():
    print("Loading feature matrix...")
    df = pd.read_parquet(DATA_PATH)

    meta_cols = ['station_id', 'station_name', 'timestamp', 'target_aqi_1h', 'target_aqi_6h', 'target_aqi_24h']
    feature_cols = [c for c in df.columns if c not in meta_cols]

    print(f"Analyzing {len(feature_cols)} features against 3 forecasting horizons across {len(df):,} samples...")

    horizons = [
        ('1h', 'target_aqi_1h'),
        ('6h', 'target_aqi_6h'),
        ('24h', 'target_aqi_24h')
    ]

    records = []
    for h_label, target_col in horizons:
        valid_mask = df[target_col].notna()
        sub_df = df[valid_mask]
        y = sub_df[target_col]

        for feat in feature_cols:
            x = sub_df[feat]
            # Valid mask for feature and target
            pair_valid = x.notna()
            if pair_valid.sum() > 100:
                corr = np.corrcoef(x[pair_valid], y[pair_valid])[0, 1]
            else:
                corr = 0.0

            records.append({
                "horizon": h_label,
                "feature": feat,
                "group": get_feature_group(feat),
                "pearson_r": round(float(corr), 4),
                "abs_r": round(float(abs(corr)), 4)
            })

    importance_df = pd.DataFrame(records)
    importance_df.sort_values(by=['horizon', 'abs_r'], ascending=[True, False], inplace=True)
    imp_path = REPORTS_DIR / "feature_importance.csv"
    importance_df.to_csv(imp_path, index=False)
    print(f"Saved feature importance rankings to: {imp_path}")

    # Copy baselines heuristic to baselines.csv
    heuristics_df = pd.read_csv(REPORTS_DIR / "baselines_heuristic.csv")
    heuristics_df.to_csv(REPORTS_DIR / "baselines.csv", index=False)
    print(f"Saved baseline metrics to: {REPORTS_DIR / 'baselines.csv'}")

    # Display Top 10 Features per Horizon
    for h_label, _ in horizons:
        print(f"\n================ Top 10 Predictive Features ({h_label}) ================")
        top_h = importance_df[importance_df['horizon'] == h_label].head(10)
        print(top_h[['feature', 'group', 'pearson_r', 'abs_r']].to_string(index=False))

    # Group-Level Summary
    print("\n================ Mean Predictive Power by Feature Group ================")
    group_summary = importance_df.groupby(['horizon', 'group'])['abs_r'].agg(['count', 'mean', 'max']).reset_index()
    group_summary.columns = ['horizon', 'group', 'num_features', 'mean_abs_r', 'max_abs_r']
    group_summary.sort_values(by=['horizon', 'mean_abs_r'], ascending=[True, False], inplace=True)
    print(group_summary.to_string(index=False))

    group_path = REPORTS_DIR / "feature_group_importance_summary.csv"
    group_summary.to_csv(group_path, index=False)

    return importance_df, group_summary


if __name__ == "__main__":
    analyze_features()

"""
baselines.py
Evaluates heuristic baseline models for multi-horizon air quality forecasting:
1. Naive Persistence: AQI(t+h) ≈ AQI(t)
2. 24h Seasonal Persistence: AQI(t+h) ≈ AQI(t+h-24)
3. Historical Moving Average: AQI(t+h) ≈ AQI_roll_mean_24h(t)
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.evaluate import compute_metrics

DATA_PATH = Path("data/processed/features_2025.parquet")
REPORTS_DIR = Path("reports/modeling")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_dataset():
    """Loads feature matrix from Parquet."""
    df = pd.read_parquet(DATA_PATH)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def split_data(df):
    """Partitions data into Train, Validation, and Test splits."""
    train_mask = (df['timestamp'] >= '2025-01-01 00:00:00+05:30') & (df['timestamp'] <= '2025-08-31 23:00:00+05:30')
    val_mask = (df['timestamp'] >= '2025-09-01 00:00:00+05:30') & (df['timestamp'] <= '2025-10-31 23:00:00+05:30')
    test_mask = (df['timestamp'] >= '2025-11-01 00:00:00+05:30') & (df['timestamp'] <= '2025-12-31 23:00:00+05:30')

    return {
        'train': df[train_mask].copy(),
        'val': df[val_mask].copy(),
        'test': df[test_mask].copy(),
        'full_year': df.copy()
    }


def add_baseline_columns(df):
    """Computes continuous causal baseline predictions across the full dataset."""
    df = df.sort_values(['station_id', 'timestamp']).copy()

    # Precalculate seasonal persistence for h=1 (t-23), h=6 (t-18), h=24 (t)
    df['pred_seasonal_1h'] = df.groupby('station_id')['aqi_curr'].shift(23)
    df['pred_seasonal_6h'] = df.groupby('station_id')['aqi_curr'].shift(18)
    df['pred_seasonal_24h'] = df['aqi_curr']  # AQI(t+24-24) = AQI(t)

    return df


def run_baselines():
    """Executes baseline evaluations across all splits and horizons."""
    print("Loading processed dataset...")
    df = load_dataset()
    df = add_baseline_columns(df)
    splits = split_data(df)

    horizons = [
        ('1h', 'target_aqi_1h', 'pred_seasonal_1h'),
        ('6h', 'target_aqi_6h', 'pred_seasonal_6h'),
        ('24h', 'target_aqi_24h', 'pred_seasonal_24h')
    ]

    records = []

    print("\n=======================================================")
    print("           EVALUATING HEURISTIC BASELINES              ")
    print("=======================================================")

    for split_name, split_df in splits.items():
        print(f"\n--- Split: {split_name.upper()} (N = {len(split_df):,}) ---")
        y_curr = split_df['aqi_curr'].values

        for h_label, target_col, seasonal_col in horizons:
            y_true = split_df[target_col].values

            # 1. Naive Persistence: AQI(t+h) ≈ AQI(t)
            y_pred_naive = y_curr
            m_naive = compute_metrics(y_true, y_pred_naive, y_curr)
            records.append({
                "model": "Naive Persistence",
                "split": split_name,
                "horizon": h_label,
                **m_naive
            })

            # 2. 24h Seasonal Persistence: AQI(t+h) ≈ AQI(t+h-24)
            y_pred_seasonal = split_df[seasonal_col].values
            m_seasonal = compute_metrics(y_true, y_pred_seasonal, y_curr)
            records.append({
                "model": "24h Seasonal Persistence",
                "split": split_name,
                "horizon": h_label,
                **m_seasonal
            })

            # 3. Historical Moving Average: AQI(t+h) ≈ aqi_roll_mean_24h(t)
            y_pred_ma = split_df['aqi_roll_mean_24h'].values
            m_ma = compute_metrics(y_true, y_pred_ma, y_curr)
            records.append({
                "model": "24h Moving Average",
                "split": split_name,
                "horizon": h_label,
                **m_ma
            })

            print(f"[{h_label}] Naive Persistence    -> MAE: {m_naive['mae']:.2f} | RMSE: {m_naive['rmse']:.2f} | R2: {m_naive['r2']:.4f}")
            print(f"[{h_label}] Seasonal Persistence -> MAE: {m_seasonal['mae']:.2f} | RMSE: {m_seasonal['rmse']:.2f} | R2: {m_seasonal['r2']:.4f}")
            print(f"[{h_label}] 24h Moving Average   -> MAE: {m_ma['mae']:.2f} | RMSE: {m_ma['rmse']:.2f} | R2: {m_ma['r2']:.4f}")

    results_df = pd.DataFrame(records)
    csv_path = REPORTS_DIR / "baselines_heuristic.csv"
    results_df.to_csv(csv_path, index=False)
    print(f"\nHeuristic baseline results saved to: {csv_path}")

    return results_df


if __name__ == "__main__":
    run_baselines()

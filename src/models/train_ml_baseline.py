"""
train_ml_baseline.py
Trains supervised machine learning regression baselines (XGBoost, HistGradientBoosting, Ridge)
for multi-horizon AQI forecasting (1h, 6h, 24h) across Delhi monitoring stations.
Computes feature importances and executes feature ablation experiments.
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.evaluate import compute_metrics

DATA_PATH = Path("data/processed/features_2025.parquet")
REPORTS_DIR = Path("reports/modeling")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Feature Group Mapping Helper
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


def load_and_prep_data():
    """Loads feature matrix and splits chronologically."""
    df = pd.read_parquet(DATA_PATH)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Feature column selection (excluding metadata and targets)
    meta_cols = ['station_id', 'station_name', 'timestamp', 'target_aqi_1h', 'target_aqi_6h', 'target_aqi_24h']
    feature_cols = [c for c in df.columns if c not in meta_cols]

    # Include station_id as an encoded feature for multi-station learning
    all_features = ['station_id'] + feature_cols

    train_mask = (df['timestamp'] >= '2025-01-01 00:00:00+05:30') & (df['timestamp'] <= '2025-08-31 23:00:00+05:30')
    val_mask = (df['timestamp'] >= '2025-09-01 00:00:00+05:30') & (df['timestamp'] <= '2025-10-31 23:00:00+05:30')
    test_mask = (df['timestamp'] >= '2025-11-01 00:00:00+05:30') & (df['timestamp'] <= '2025-12-31 23:00:00+05:30')

    return df, all_features, train_mask, val_mask, test_mask


def train_and_eval_models():
    """Trains XGBoost, HistGradientBoosting, and Ridge across all 3 horizons."""
    df, features, train_mask, val_mask, test_mask = load_and_prep_data()

    horizons = [
        ('1h', 'target_aqi_1h'),
        ('6h', 'target_aqi_6h'),
        ('24h', 'target_aqi_24h')
    ]

    records = []
    importance_records = []

    print("\n=======================================================")
    print("        TRAINING SUPERVISED ML REGRESSION BASELINES    ")
    print("=======================================================")

    for h_label, target_col in horizons:
        print(f"\n#######################################################")
        print(f"            HORIZON: {h_label.upper()} ({target_col})")
        print(f"#######################################################")

        # Create valid horizon masks (dropping rows where target is NaN)
        valid_target = df[target_col].notna()

        tr_idx = train_mask & valid_target
        va_idx = val_mask & valid_target
        te_idx = test_mask & valid_target

        X_train = df.loc[tr_idx, features]
        y_train = df.loc[tr_idx, target_col].values
        c_train = df.loc[tr_idx, 'aqi_curr'].values

        X_val = df.loc[va_idx, features]
        y_val = df.loc[va_idx, target_col].values
        c_val = df.loc[va_idx, 'aqi_curr'].values

        X_test = df.loc[te_idx, features]
        y_test = df.loc[te_idx, target_col].values
        c_test = df.loc[te_idx, 'aqi_curr'].values

        # -------------------------------------------------------------
        # 1. Primary Model: XGBoost Regressor (Histogram-based)
        # -------------------------------------------------------------
        print(f"\n--- [1] Training XGBoost Regressor ({h_label}) ---")
        t0 = time.time()
        xgb = XGBRegressor(
            n_estimators=150,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            tree_method='hist',
            random_state=42,
            n_jobs=2,
        )
        xgb.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        t_fit = time.time() - t0
        print(f"XGBoost fit completed in {t_fit:.2f}s")

        # Evaluate XGBoost across splits
        for split_name, X_s, y_s, c_s in [('train', X_train, y_train, c_train),
                                          ('val', X_val, y_val, c_val),
                                          ('test', X_test, y_test, c_test)]:
            p_s = xgb.predict(X_s)
            m = compute_metrics(y_s, p_s, c_s)
            records.append({
                "model": "XGBoost Regressor",
                "split": split_name,
                "horizon": h_label,
                **m
            })
            print(f"XGBoost [{split_name.upper():5s}] -> MAE: {m['mae']:.2f} | RMSE: {m['rmse']:.2f} | R2: {m['r2']:.4f} | Extreme MAE: {m['extreme_mae']}")

        # Full year evaluation
        full_idx = valid_target
        X_full = df.loc[full_idx, features]
        y_full = df.loc[full_idx, target_col].values
        c_full = df.loc[full_idx, 'aqi_curr'].values
        p_full = xgb.predict(X_full)
        m_full = compute_metrics(y_full, p_full, c_full)
        records.append({
            "model": "XGBoost Regressor",
            "split": "full_year",
            "horizon": h_label,
            **m_full
        })

        # Feature importances for XGBoost
        importances = xgb.feature_importances_
        for feat_name, imp in zip(features, importances):
            importance_records.append({
                "horizon": h_label,
                "feature": feat_name,
                "importance": float(imp),
                "group": get_feature_group(feat_name)
            })

        # -------------------------------------------------------------
        # 2. Benchmark Model: HistGradientBoostingRegressor
        # -------------------------------------------------------------
        print(f"\n--- [2] Training HistGradientBoostingRegressor ({h_label}) ---")
        t0 = time.time()
        hgbr = HistGradientBoostingRegressor(
            max_iter=150,
            max_depth=6,
            learning_rate=0.08,
            random_state=42
        )
        hgbr.fit(X_train, y_train)
        print(f"HistGradientBoosting fit completed in {time.time() - t0:.2f}s")

        for split_name, X_s, y_s, c_s in [('train', X_train, y_train, c_train),
                                          ('val', X_val, y_val, c_val),
                                          ('test', X_test, y_test, c_test)]:
            p_s = hgbr.predict(X_s)
            m = compute_metrics(y_s, p_s, c_s)
            records.append({
                "model": "HistGradientBoosting",
                "split": split_name,
                "horizon": h_label,
                **m
            })
            print(f"HGBR    [{split_name.upper():5s}] -> MAE: {m['mae']:.2f} | RMSE: {m['rmse']:.2f} | R2: {m['r2']:.4f}")

        # -------------------------------------------------------------
        # 3. Benchmark Model: Linear Ridge Regression
        # -------------------------------------------------------------
        print(f"\n--- [3] Training Ridge Regression ({h_label}) ---")
        # Impute missing values with train column medians for linear model
        medians = X_train.median()
        X_tr_imp = X_train.fillna(medians)
        X_va_imp = X_val.fillna(medians)
        X_te_imp = X_test.fillna(medians)

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr_imp)
        X_va_s = scaler.transform(X_va_imp)
        X_te_s = scaler.transform(X_te_imp)

        ridge = Ridge(alpha=100.0)
        ridge.fit(X_tr_s, y_train)

        for split_name, X_s, y_s, c_s in [('train', X_tr_s, y_train, c_train),
                                          ('val', X_va_s, y_val, c_val),
                                          ('test', X_te_s, y_test, c_test)]:
            p_s = ridge.predict(X_s)
            m = compute_metrics(y_s, p_s, c_s)
            records.append({
                "model": "Ridge Regression",
                "split": split_name,
                "horizon": h_label,
                **m
            })
            print(f"Ridge   [{split_name.upper():5s}] -> MAE: {m['mae']:.2f} | RMSE: {m['rmse']:.2f} | R2: {m['r2']:.4f}")

    # Combine with heuristic baselines
    ml_results_df = pd.DataFrame(records)
    heuristics_df = pd.read_csv(REPORTS_DIR / "baselines_heuristic.csv")
    all_baselines = pd.concat([heuristics_df, ml_results_df], ignore_index=True)
    all_baselines.to_csv(REPORTS_DIR / "baselines.csv", index=False)
    print(f"\nAll baseline benchmarks saved to: {REPORTS_DIR / 'baselines.csv'}")

    # Feature Importance Export
    imp_df = pd.DataFrame(importance_records)
    imp_df.to_csv(REPORTS_DIR / "feature_importance.csv", index=False)
    print(f"Feature importances saved to: {REPORTS_DIR / 'feature_importance.csv'}")

    # Feature Group Importance Aggregation
    group_imp = imp_df.groupby(['horizon', 'group'])['importance'].sum().reset_index()
    print("\n=== Feature Importance by Group (Summed Normalized Gain) ===")
    for h, gh in group_imp.groupby('horizon'):
        print(f"\n--- Horizon: {h} ---")
        print(gh.sort_values('importance', ascending=False).to_string(index=False))

    return all_baselines, imp_df


def run_feature_ablations():
    """Executes ablation experiments across different feature subsets."""
    df, features, train_mask, val_mask, test_mask = load_and_prep_data()

    # Define feature subsets
    group_map = {c: get_feature_group(c) for c in features}

    subsets = {
        "Full Feature Set (Groups A-G)": features,
        "Group A Only (AQI Lags Only)": [c for c in features if group_map[c] in ['Group A: Recent AQI Lags', 'Station Metadata']],
        "No Meteorology (Exclude Group F)": [c for c in features if group_map[c] != 'Group F: Meteorology'],
        "No Spatial Signals (Exclude Group G)": [c for c in features if group_map[c] != 'Group G: Cross-Station Spatial'],
        "No Pollutant Lags (Exclude Group B)": [c for c in features if group_map[c] != 'Group B: Pollutant Lags'],
        "No Rolling Stats (Exclude Group C)": [c for c in features if group_map[c] != 'Group C: Causal Rolling Statistics'],
        "Raw Temporal Only (No Cyclical)": [c for c in features if not c.startswith(('sin_', 'cos_'))],
    }

    ablation_records = []
    print("\n=======================================================")
    print("              RUNNING FEATURE ABLATION EXPERIMENTS     ")
    print("=======================================================")

    for subset_name, subset_cols in subsets.items():
        print(f"\n--- Testing Subset: {subset_name} ({len(subset_cols)} features) ---")

        for h_label, target_col in [('1h', 'target_aqi_1h'), ('6h', 'target_aqi_6h'), ('24h', 'target_aqi_24h')]:
            valid_target = df[target_col].notna()
            tr_idx = train_mask & valid_target
            va_idx = val_mask & valid_target
            te_idx = test_mask & valid_target

            X_tr = df.loc[tr_idx, subset_cols]
            y_tr = df.loc[tr_idx, target_col].values
            c_tr = df.loc[tr_idx, 'aqi_curr'].values

            X_va = df.loc[va_idx, subset_cols]
            y_va = df.loc[va_idx, target_col].values
            c_va = df.loc[va_idx, 'aqi_curr'].values

            X_te = df.loc[te_idx, subset_cols]
            y_te = df.loc[te_idx, target_col].values
            c_te = df.loc[te_idx, 'aqi_curr'].values

            xgb = XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.08,
                tree_method='hist',
                random_state=42,
                n_jobs=2,
            )
            xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)

            m_val = compute_metrics(y_va, xgb.predict(X_va), c_va)
            m_test = compute_metrics(y_te, xgb.predict(X_te), c_te)

            ablation_records.append({
                "experiment": subset_name,
                "num_features": len(subset_cols),
                "horizon": h_label,
                "val_mae": m_val['mae'],
                "val_rmse": m_val['rmse'],
                "val_r2": m_val['r2'],
                "test_mae": m_test['mae'],
                "test_rmse": m_test['rmse'],
                "test_r2": m_test['r2'],
                "test_extreme_mae": m_test['extreme_mae'],
            })

            print(f"[{h_label:3s}] Val MAE: {m_val['mae']:.2f} | Test MAE: {m_test['mae']:.2f} | Test RMSE: {m_test['rmse']:.2f} | Test R2: {m_test['r2']:.4f}")

    ablation_df = pd.DataFrame(ablation_records)
    ablation_df.to_csv(REPORTS_DIR / "ablation_results.csv", index=False)
    print(f"\nAblation results saved to: {REPORTS_DIR / 'ablation_results.csv'}")

    return ablation_df


if __name__ == "__main__":
    train_and_eval_models()
    run_feature_ablations()

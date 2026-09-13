"""
evaluate.py
Standardized evaluation metrics for multi-horizon air quality forecasting.
Calculates MAE, RMSE, R2, MAPE, Extreme Episode MAE (AQI >= 300), and Directional Accuracy.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def compute_metrics(y_true, y_pred, y_curr=None):
    """
    Computes regression evaluation metrics.

    Parameters:
    -----------
    y_true : array-like
        Ground-truth future AQI values.
    y_pred : array-like
        Predicted future AQI values.
    y_curr : array-like, optional
        Current AQI baseline at forecast issuance time t (for directional accuracy).

    Returns:
    --------
    dict containing MAE, RMSE, R2, MAPE, Extreme MAE (>= 300), and Directional Accuracy.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    # Filter out NaNs
    valid_mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if y_curr is not None:
        y_curr = np.asarray(y_curr, dtype=float)
        valid_mask = valid_mask & np.isfinite(y_curr)

    y_t = y_true[valid_mask]
    y_p = y_pred[valid_mask]

    if len(y_t) == 0:
        return {
            "n_samples": 0,
            "mae": np.nan,
            "rmse": np.nan,
            "r2": np.nan,
            "mape": np.nan,
            "extreme_mae": np.nan,
            "directional_accuracy": np.nan,
        }

    # Core metrics
    mae = mean_absolute_error(y_t, y_p)
    rmse = np.sqrt(mean_squared_error(y_t, y_p))
    r2 = r2_score(y_t, y_p)

    # MAPE (avoiding division by zero by clipping denominator to min 1.0)
    denom = np.clip(np.abs(y_t), 1.0, None)
    mape = np.mean(np.abs(y_t - y_p) / denom) * 100.0

    # Extreme Episode MAE (AQI >= 300: Severe / Hazardous)
    extreme_mask = y_t >= 300.0
    if np.any(extreme_mask):
        extreme_mae = mean_absolute_error(y_t[extreme_mask], y_p[extreme_mask])
    else:
        extreme_mae = np.nan

    # Directional Accuracy
    if y_curr is not None:
        y_c = y_curr[valid_mask]
        actual_dir = np.sign(y_t - y_c)
        pred_dir = np.sign(y_p - y_c)
        # Match when directions agree or both are 0
        dir_acc = np.mean(actual_dir == pred_dir) * 100.0
    else:
        dir_acc = np.nan

    return {
        "n_samples": int(len(y_t)),
        "mae": round(float(mae), 3),
        "rmse": round(float(rmse), 3),
        "r2": round(float(r2), 4),
        "mape": round(float(mape), 2),
        "extreme_mae": round(float(extreme_mae), 3) if np.isfinite(extreme_mae) else np.nan,
        "directional_accuracy": round(float(dir_acc), 2) if np.isfinite(dir_acc) else np.nan,
    }

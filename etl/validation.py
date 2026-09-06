# etl/validation.py
import pandas as pd
import numpy as np
from schemas import SENTINEL_VALUES, PHYSICAL_BOUNDS

def validate_and_clean_df(df: pd.DataFrame, source_type: str) -> tuple[pd.DataFrame, dict]:
    """
    Applies sentinel deletion and physical bounds checking.
    Returns cleaned DF and stats dict.
    """
    stats = {
        "sentinel_replacements": 0,
        "out_of_bounds_replacements": 0,
        "rows_total": len(df)
    }

    # 1. Nullify exactly matched Sentinels
    for col in df.columns:
        if col in ["ts", "station_id", "source_file_id"]: continue
        if pd.api.types.is_numeric_dtype(df[col]):
            mask = df[col].isin(SENTINEL_VALUES)
            hits = mask.sum()
            if hits > 0:
                stats["sentinel_replacements"] += int(hits)
                df.loc[mask, col] = np.nan

    # 2. Check Physical bounds
    for col in df.columns:
        if col in PHYSICAL_BOUNDS and col in df.columns:
            min_val, max_val = PHYSICAL_BOUNDS[col]
            if min_val is not None:
                mask = df[col] < min_val
                hits = mask.sum()
                if hits > 0:
                    stats["out_of_bounds_replacements"] += int(hits)
                    df.loc[mask, col] = np.nan
            if max_val is not None:
                mask = df[col] > max_val
                hits = mask.sum()
                if hits > 0:
                    stats["out_of_bounds_replacements"] += int(hits)
                    df.loc[mask, col] = np.nan

    return df, stats

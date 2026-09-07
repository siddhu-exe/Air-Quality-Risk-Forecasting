import pandas as pd
import numpy as np
import json
from schemas import SENTINEL_VALUES, PHYSICAL_BOUNDS

def validate_and_clean_df(df: pd.DataFrame, source_type: str) -> tuple[pd.DataFrame, dict]:
    stats = {
        "sentinel_replacements": 0,
        "out_of_bounds_replacements": 0,
        "qc_flagged_rows": 0,
        "rows_total": len(df),
    }

    # Resetting index so position indexing matches the row array
    df = df.reset_index(drop=True)
    qc_acc = [{} for _ in range(len(df))]

    # 1. Nullify sentinel values
    for col in df.columns:
        if col in ("ts", "station_id", "source_file_id", "qc_flags"):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            mask = df[col].isin(SENTINEL_VALUES)
            hits = mask.sum()
            if hits > 0:
                stats["sentinel_replacements"] += int(hits)
                # True indices
                idx = np.where(mask)[0]
                for pos in idx:
                    raw_val = df.at[pos, col]
                    qc_acc[pos][col] = f"SENTINEL_{raw_val}"
                df.loc[mask, col] = np.nan

    # 2. Check physical bounds
    for col in df.columns:
        if col not in PHYSICAL_BOUNDS:
            continue
        min_val, max_val = PHYSICAL_BOUNDS[col]
        if min_val is not None:
            mask = df[col].notna() & (df[col] < min_val)
            hits = mask.sum()
            if hits > 0:
                stats["out_of_bounds_replacements"] += int(hits)
                idx = np.where(mask)[0]
                for pos in idx:
                    raw_val = df.at[pos, col]
                    qc_acc[pos][col] = f"OOB_BELOW_{min_val}(was_{raw_val})"
                df.loc[mask, col] = np.nan
        if max_val is not None:
            mask = df[col].notna() & (df[col] > max_val)
            hits = mask.sum()
            if hits > 0:
                stats["out_of_bounds_replacements"] += int(hits)
                idx = np.where(mask)[0]
                for pos in idx:
                    raw_val = df.at[pos, col]
                    qc_acc[pos][col] = f"OOB_ABOVE_{max_val}(was_{raw_val})"
                df.loc[mask, col] = np.nan

    df["qc_flags"] = [json.dumps(d) if d else None for d in qc_acc]
    flagged = sum(1 for d in qc_acc if d)
    stats["qc_flagged_rows"] = flagged

    return df, stats

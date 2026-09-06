# etl/transform_caaqms.py
from pathlib import Path
import pandas as pd
from schemas import CSV_COLUMN_MAPPING, CAAQMS_DB_COLUMNS
from validation import validate_and_clean_df

def process_caaqms_csv(file_path: Path) -> tuple[pd.DataFrame | None, dict]:
    stats = {"status": "ok", "error": None, "raw_rows": 0, "processed_rows": 0, "dropped_invalid_ts": 0}
    try:
        # Load raw data
        df = pd.read_csv(file_path, na_values=["NA", "na", "N/A", "n/a", "--", ""],
                         keep_default_na=True, low_memory=False)
        stats["raw_rows"] = len(df)

        # Standarize Columns
        # Rename those matching our mapping, drop remainder except what's needed
        df = df.rename(columns=CSV_COLUMN_MAPPING)

        # Retain only recognized columns
        keep_cols = [c for c in CAAQMS_DB_COLUMNS if c in df.columns]
        # Always retain 'ts' if present
        if "ts" not in keep_cols and "ts" in df.columns:
            keep_cols.append("ts")

        df = df[keep_cols].copy()

        # Fix Timestamps
        if "ts" in df.columns:
            # Coerce errors -> NaT
            df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

            # Remove bad epoch parsing (1970)
            bad_epoch = pd.to_datetime("1970-01-01")
            is_valid_ts = df["ts"].notna() & (df["ts"] > bad_epoch)

            stats["dropped_invalid_ts"] = int((~is_valid_ts).sum())
            df = df[is_valid_ts].copy()

            # Set timezone to IST (Asia/Kolkata)
            # If already tz-aware, convert, else localize
            if not df.empty:
                if df["ts"].dt.tz is None:
                    df["ts"] = df["ts"].dt.tz_localize("Asia/Kolkata")
                else:
                    df["ts"] = df["ts"].dt.tz_convert("Asia/Kolkata")

        # Deduplicate internal (station, ts) by taking last entry
        if "ts" in df.columns:
            df = df.drop_duplicates(subset=["ts"], keep="last")

        df, clean_stats = validate_and_clean_df(df, "CAAQMS")
        stats.update(clean_stats)
        stats["processed_rows"] = len(df)

        return df, stats

    except Exception as e:
        stats["status"] = "error"
        stats["error"] = str(e)
        return None, stats

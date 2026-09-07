import os
from pathlib import Path
import pandas as pd
import numpy as np

# Use the existing ETL modules
try:
    from schemas import CSV_COLUMN_MAPPING, CAAQMS_DB_COLUMNS, SENTINEL_VALUES, PHYSICAL_BOUNDS, clean_station_name
    from transform_caaqms import process_caaqms_csv
    from discover import discover_files
except ImportError:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), 'etl'))
    from schemas import CSV_COLUMN_MAPPING, CAAQMS_DB_COLUMNS, SENTINEL_VALUES, PHYSICAL_BOUNDS, clean_station_name
    from transform_caaqms import process_caaqms_csv
    from discover import discover_files

DATA_ROOT = Path(__file__).resolve().parent.parent / "Og Data" / "Delhi data"

def audit_quality_hits():
    files = discover_files(DATA_ROOT)

    hits = []
    ts_drops = 0
    total_raw_rows = 0
    total_retained_rows = 0

    for meta in files:
        path = meta["path"]
        if meta["ext"] != ".csv":
            # the sentinels were mostly in CAAQMS andAQI. wait, let's check AQI too
            continue

        # We will manually do the transform to audit the data
        df = pd.read_csv(path, na_values=["NA", "na", "N/A", "n/a", "--", ""], keep_default_na=True, low_memory=False)
        total_raw_rows += len(df)

        df = df.rename(columns=CSV_COLUMN_MAPPING)
        keep_cols = [c for c in CAAQMS_DB_COLUMNS if c in df.columns]
        if "ts" not in keep_cols and "ts" in df.columns:
            keep_cols.append("ts")
        df = df[keep_cols].copy()

        if "ts" in df.columns:
            df["ts_raw"] = df["ts"]
            df["ts_parsed"] = pd.to_datetime(df["ts"], errors="coerce")
            bad_epoch = pd.to_datetime("1970-01-01")

            invalid_mask = df["ts_parsed"].isna() | (df["ts_parsed"] <= bad_epoch)
            ts_drop_count = invalid_mask.sum()
            if ts_drop_count > 0:
                ts_drops += ts_drop_count

            df = df[~invalid_mask].copy()
            df = df.drop_duplicates(subset=["ts_parsed"], keep="last")

        total_retained_rows += len(df)

        # Check sentinels and bounds
        for col in df.columns:
            if col in ["ts", "ts_raw", "ts_parsed", "station_id", "source_file_id"]: continue
            if pd.api.types.is_numeric_dtype(df[col]):
                # sentinels
                sentinel_mask = df[col].isin(SENTINEL_VALUES)
                if sentinel_mask.sum() > 0:
                    bad_vals = df.loc[sentinel_mask, col].value_counts().to_dict()
                    for val, count in bad_vals.items():
                        hits.append({
                            "file": path.name,
                            "station": meta["station_folder"],
                            "column": col,
                            "rule": "sentinel",
                            "value": val,
                            "count": count
                        })

                # out of bounds
                if col in PHYSICAL_BOUNDS:
                    min_val, max_val = PHYSICAL_BOUNDS[col]
                    if min_val is not None:
                        # Exclude sentinels from oob check since they are processed first in real code
                        oob_mask = (df[col] < min_val) & (~sentinel_mask)
                        if oob_mask.sum() > 0:
                            bad_vals = df.loc[oob_mask, col].value_counts().head(5).to_dict()
                            hits.append({
                                "file": path.name,
                                "station": meta["station_folder"],
                                "column": col,
                                "rule": f"negative_or_below_min_{min_val}",
                                "value": str(bad_vals),
                                "count": oob_mask.sum()
                            })
                    if max_val is not None:
                        oob_mask = (df[col] > max_val) & (~sentinel_mask)
                        if oob_mask.sum() > 0:
                            bad_vals = df.loc[oob_mask, col].value_counts().head(5).to_dict()
                            hits.append({
                                "file": path.name,
                                "station": meta["station_folder"],
                                "column": col,
                                "rule": f"above_max_{max_val}",
                                "value": str(bad_vals),
                                "count": oob_mask.sum()
                            })

    # Let's also check AQI files
    for meta in files:
        if meta["ext"] != ".xlsx": continue

        path = meta["path"]
        xl = pd.ExcelFile(path, engine="openpyxl")
        for sheet in xl.sheet_names:
            df = xl.parse(sheet, na_values=["NA", "na", "N/A", "n/a", "--", ""], keep_default_na=True)
            if "Date" not in df.columns: continue
            time_cols = [c for c in df.columns if isinstance(c, str) and ":" in c and len(c) >= 5]
            melted = pd.melt(df, id_vars=["Date"], value_vars=time_cols, var_name="HourStr", value_name="aqi")
            melted = melted.dropna(subset=["aqi"])
            melted["DateStr"] = pd.to_datetime(melted["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
            melted = melted.dropna(subset=["DateStr"])
            melted["ts_str"] = melted["DateStr"] + " " + melted["HourStr"].astype(str)
            melted["ts"] = pd.to_datetime(melted["ts_str"], errors="coerce")
            bad_epoch = pd.to_datetime("1970-01-01")

            invalid_mask = melted["ts"].isna() | (melted["ts"] <= bad_epoch)
            ts_drops += invalid_mask.sum()
            melted = melted[~invalid_mask].copy()

            if pd.api.types.is_numeric_dtype(melted["aqi"]):
                sentinel_mask = melted["aqi"].isin(SENTINEL_VALUES)
                if sentinel_mask.sum() > 0:
                    bad_vals = melted.loc[sentinel_mask, "aqi"].value_counts().to_dict()
                    for val, count in bad_vals.items():
                        hits.append({
                            "file": path.name,
                            "station": meta["station_folder"],
                            "column": "aqi",
                            "rule": "sentinel",
                            "value": val,
                            "count": count
                        })
                # No physical bounds explicitly defined for AQI yet, but usually > 0

    import json
    df_hits = pd.DataFrame(hits)

    report = {
        "TS_DROPS": int(ts_drops),
        "RAW_CSV_ROWS": int(total_raw_rows),
        "RETAINED_CSV_ROWS": int(total_retained_rows)
    }

    if not df_hits.empty:
        summary = df_hits.groupby(["rule", "column", "value"])["count"].sum().reset_index()
        report["SUMMARY"] = summary.to_dict(orient="records")
        # Give examples of files
        examples = df_hits.groupby(["rule", "column", "value"]).first().reset_index()
        report["EXAMPLES"] = examples.to_dict(orient="records")

    print("AUDIT_JSON_START")
    print(json.dumps(report, indent=2))
    print("AUDIT_JSON_END")

if __name__ == "__main__":
    audit_quality_hits()

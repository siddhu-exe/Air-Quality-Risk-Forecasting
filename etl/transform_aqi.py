# etl/transform_aqi.py
from pathlib import Path
import pandas as pd
from validation import validate_and_clean_df

def process_aqi_xlsx(file_path: Path) -> tuple[pd.DataFrame | None, dict]:
    stats = {"status": "ok", "error": None, "raw_rows": 0, "processed_rows": 0, "dropped_invalid_ts": 0}
    try:
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        all_sheets_data = []

        for sheet in xl.sheet_names:
            df = xl.parse(sheet, na_values=["NA", "na", "N/A", "n/a", "--", ""], keep_default_na=True)
            stats["raw_rows"] += len(df)

            if "Date" not in df.columns:
                continue

            # Identify time columns: 00:00:00, 01:00:00, etc.
            time_cols = [c for c in df.columns if isinstance(c, str) and ":" in c and len(c) >= 5]

            # Melt wide to long
            melted = pd.melt(df, id_vars=["Date"], value_vars=time_cols,
                             var_name="HourStr", value_name="aqi")

            # Drop null AQI upfront for efficiency
            melted = melted.dropna(subset=["aqi"])

            # Reconstruct Timestamp
            # df['Date'] might be datetime or string. Coerce to string date.
            melted["DateStr"] = pd.to_datetime(melted["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
            melted = melted.dropna(subset=["DateStr"])

            melted["ts_str"] = melted["DateStr"] + " " + melted["HourStr"].astype(str)
            melted["ts"] = pd.to_datetime(melted["ts_str"], errors="coerce")

            # Remove invalid
            bad_epoch = pd.to_datetime("1970-01-01")
            is_valid_ts = melted["ts"].notna() & (melted["ts"] > bad_epoch)
            stats["dropped_invalid_ts"] += int((~is_valid_ts).sum())
            melted = melted[is_valid_ts].copy()

            # Set Tz
            if not melted.empty:
                if melted["ts"].dt.tz is None:
                    melted["ts"] = melted["ts"].dt.tz_localize("Asia/Kolkata")
                else:
                    melted["ts"] = melted["ts"].dt.tz_convert("Asia/Kolkata")

            melted["aqi"] = pd.to_numeric(melted["aqi"], errors="coerce")
            all_sheets_data.append(melted[["ts", "aqi"]])

        if not all_sheets_data:
            return pd.DataFrame(), stats

        final_df = pd.concat(all_sheets_data, ignore_index=True)
        final_df = final_df.drop_duplicates(subset=["ts"], keep="last")

        final_df, clean_stats = validate_and_clean_df(final_df, "AQI")
        stats.update(clean_stats)
        stats["processed_rows"] = len(final_df)

        return final_df, stats

    except Exception as e:
        stats["status"] = "error"
        stats["error"] = str(e)
        return None, stats

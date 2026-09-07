import os
import argparse
from pathlib import Path
import pandas as pd

from schemas import clean_station_name
from discover import discover_files
from transform_caaqms import process_caaqms_csv
from transform_aqi import process_aqi_xlsx

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_ROOT = PROJECT_ROOT / "Og Data" / "Delhi data"
MUMBAI_ROOT = PROJECT_ROOT / "Og Data" / "Mumbai data"

def run_dry_run():
    print(f"\n{'='*60}")
    print("  Air Quality ETL Pipeline — DRY RUN")
    print(f"{'='*60}\n")

    files = discover_files(DATA_ROOT)
    files.extend(discover_files(MUMBAI_ROOT))
    
    print(f"Discovered {len(files)} files to process.")

    global_stats = {
        "files_processed": 0,
        "files_failed": 0,
        "caaqms_rows_staged": 0,
        "aqi_rows_staged": 0,
        "dropped_epoch_ts": 0,
        "dropped_epoch_ts_aqi": 0,
        "total_sentinels": 0,
        "total_oob": 0,
        "qc_flagged_rows": 0
    }

    stations_discovered = {}
    
    # Check bounds
    min_ts, max_ts = None, None
    total_records = 0

    import time
    start = time.time()

    for i, meta in enumerate(files):
        path = meta["path"]
        ext = meta["ext"]
        station_raw = meta.get("station_folder", "Mumbai City")
        if "mumbai" in str(path).lower():
            station_raw = "Mumbai City"

        if station_raw not in stations_discovered:
            clean_name, city, op = clean_station_name(station_raw)
            if station_raw == "Mumbai City": 
                clean_name, city, op = "Mumbai City", "Mumbai", "Unknown"
            stations_discovered[station_raw] = {
                "clean_name": clean_name, "city": city, "operator": op, "obs": 0
            }

        print(f"[{i+1}/{len(files)}] Processing: {path.name} ", end="")

        if ext == ".csv":
            df, stats = process_caaqms_csv(path)
            mode = "CAAQMS"
        else:
            df, stats = process_aqi_xlsx(path)
            mode = "AQI"

        if stats["status"] == "error":
            print(f" [FAILED] - {stats['error']}")
            global_stats["files_failed"] += 1
            continue

        valid_rows = stats['processed_rows']
        dropped_ts = stats.get('dropped_invalid_ts', 0)
        
        if mode == "CAAQMS":
            global_stats["caaqms_rows_staged"] += valid_rows
            global_stats["dropped_epoch_ts"] += dropped_ts
        else:
            global_stats["aqi_rows_staged"] += valid_rows
            global_stats["dropped_epoch_ts_aqi"] += dropped_ts
            
        print(f" [OK] - {valid_rows} rows staged (Dropped Invalid TS: {dropped_ts})")

        global_stats["files_processed"] += 1
        global_stats["total_sentinels"] += stats.get("sentinel_replacements", 0)
        global_stats["total_oob"] += stats.get("out_of_bounds_replacements", 0)
        global_stats["qc_flagged_rows"] += stats.get("qc_flagged_rows", 0)
        
        stations_discovered[station_raw]["obs"] += valid_rows
        
        if df is not None and not df.empty and "ts" in df.columns:
            f_min = df["ts"].min()
            f_max = df["ts"].max()
            if min_ts is None or f_min < min_ts: min_ts = f_min
            if max_ts is None or f_max > max_ts: max_ts = f_max

    end = time.time()
    
    print(f"\n{'='*60}")
    print("  DRY RUN RESULTS")
    print(f"{'='*60}")
    print(f"  Stations normalized: {len(stations_discovered)}")
    for raw, details in stations_discovered.items():
        print(f"    - '{raw}' -> '{details['clean_name']}' ({details['obs']:,} observations)")

    print("\n  Data Yield:")
    print(f"    - Files Discovered: {len(files)}")
    print(f"    - Files Processed: {global_stats['files_processed']}")
    print(f"    - Files Failed: {global_stats['files_failed']}")
    print(f"    - CAAQMS insert-ready records: {global_stats['caaqms_rows_staged']:,}")
    print(f"    - AQI insert-ready records: {global_stats['aqi_rows_staged']:,}")
    print(f"    - Total Date Range: {min_ts} to {max_ts}")
    print(f"    - Total Time Elapsed: {round(end-start, 2)} seconds")

    print("\n  Invalid Timestamps (Dropped Records):")
    print(f"    - CAAQMS: {global_stats['dropped_epoch_ts']:,}")
    print(f"    - AQI string/unrecoverable: {global_stats['dropped_epoch_ts_aqi']:,}")

    print("\n  Data Quality Modifications (qc_flags):")
    print(f"    - Rows with at least one QC flag: {global_stats['qc_flagged_rows']:,}")
    print(f"    - Sentinel placeholders nulled: {global_stats['total_sentinels']:,}")
    print(f"    - Out-of-bounds metrics nulled: {global_stats['total_oob']:,}")
    
    print("\n  (Dry run complete. No database changes were made.)\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Air Quality ETL Pipeline")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run without DB inserts")
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run()
    else:
        print("Database insert pipeline not yet activated. Exiting.")

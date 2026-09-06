# pipeline.py
import os
import argparse
from pathlib import Path
import pandas as pd

# Adjust imports to treat 'etl' as a module
from schemas import clean_station_name
from discover import discover_files
from transform_caaqms import process_caaqms_csv
from transform_aqi import process_aqi_xlsx
# from load_postgres import load_data_to_db

# ---------------------------------------------------------------------------
# Core Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_ROOT = PROJECT_ROOT / "Og Data" / "Delhi data"

# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------
def run_dry_run():
    print(f"\n{'='*60}")
    print("  Delhi Air Quality ETL Pipeline — DRY RUN")
    print(f"{'='*60}\n")

    files = discover_files(DATA_ROOT)
    print(f"Discovered {len(files)} files to process.")

    global_stats = {
        "files_processed": 0,
        "files_failed": 0,
        "caaqms_rows_staged": 0,
        "aqi_rows_staged": 0,
        "total_sentinels": 0,
        "total_oob": 0
    }

    # Tracking unique stations discovered
    stations_discovered = {}

    for i, meta in enumerate(files):
        path = meta["path"]
        ext = meta["ext"]
        station_raw = meta["station_folder"]

        # Normalize station
        if station_raw not in stations_discovered:
            clean_name, city, op = clean_station_name(station_raw)
            stations_discovered[station_raw] = {
                "clean_name": clean_name, "city": city, "operator": op
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

        print(f" [OK] - {stats['processed_rows']} valid rows (Raw: {stats['raw_rows']}, Dropped TS: {stats.get('dropped_invalid_ts', 0)})")

        global_stats["files_processed"] += 1
        if mode == "CAAQMS":
            global_stats["caaqms_rows_staged"] += stats["processed_rows"]
        else:
            global_stats["aqi_rows_staged"] += stats["processed_rows"]

        global_stats["total_sentinels"] += stats.get("sentinel_replacements", 0)
        global_stats["total_oob"] += stats.get("out_of_bounds_replacements", 0)

    print(f"\n{'='*60}")
    print("  DRY RUN RESULTS")
    print(f"{'='*60}")
    print(f"  Stations normalized: {len(stations_discovered)}")
    for raw, details in stations_discovered.items():
        print(f"    - '{raw}' -> '{details['clean_name']}'")

    print("\n  Data Yield:")
    print(f"    - Files OK: {global_stats['files_processed']}")
    print(f"    - Files Failed: {global_stats['files_failed']}")
    print(f"    - CAAQMS insert-ready records: {global_stats['caaqms_rows_staged']:,}")
    print(f"    - AQI insert-ready records: {global_stats['aqi_rows_staged']:,}")

    print("\n  Data Quality Modifications:")
    print(f"    - Sentinel placeholders nulled: {global_stats['total_sentinels']:,}")
    print(f"    - Invalid out-of-bounds nulled: {global_stats['total_oob']:,}")
    print("\n  (Dry run complete. No database changes were made.)\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Air Quality ETL Pipeline")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run without DB inserts")
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run()
    else:
        print("Database insert pipeline not yet activated. Exiting.")

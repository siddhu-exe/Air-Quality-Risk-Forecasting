"""
run_full_load.py

Executes the full production ETL ingestion for all Delhi stations.
Discovers all files, processes them, and inserts idempotently into PostgreSQL.
Halts immediately on any failure to preserve data integrity.
"""

from __future__ import annotations

import sys
import json
import traceback
from pathlib import Path

# Add ETL dir to path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_DIR / "etl"))

from load_postgres import (
    load_env, get_connection, get_or_create_station, get_or_create_source_file,
    insert_caaqms_batch, insert_aqi_batch
)
from transform_caaqms import process_caaqms_csv
from transform_aqi import process_aqi_xlsx
from discover import discover_files
from schemas import clean_station_name


def main():
    print("=== STARTING FULL PRODUCTION ETL LOAD ===")
    print("Scope: All Delhi stations")

    env = load_env()
    conn = get_connection(env)
    conn.autocommit = False

    data_root = PROJECT_DIR / "Og Data" / "Delhi data"
    files = discover_files(data_root)

    print(f"\n[DISCOVERY] Found {len(files)} files in Delhi data directory.")
    if len(files) == 0:
        print("No files found! Exiting.")
        return

    # PRE-LOAD AUDIT
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM stations")
        pre_stations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM source_files")
        pre_files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM caaqms_hourly")
        pre_caaqms = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM aqi_hourly")
        pre_aqi = cur.fetchone()[0]

    print(f"\n[PRE-LOAD AUDIT]")
    print(f"  stations:      {pre_stations}")
    print(f"  source_files:  {pre_files}")
    print(f"  caaqms_hourly: {pre_caaqms}")
    print(f"  aqi_hourly:    {pre_aqi}")
    print("  Load uses ON CONFLICT DO UPDATE for idempotency. Existing Jan 2025 data will remain intact (overwritten with same values).")

    stats_report = []

    for fmeta in files:
        path = fmeta["path"]
        ext = fmeta["ext"]
        station_folder = fmeta["station_folder"]

        filename = path.name
        print(f"\n[PROCESSING] {filename} ({station_folder})")

        station_name, city, operator = clean_station_name(station_folder)

        file_record = {
            "filename": filename,
            "station": station_name,
            "type": "CAAQMS" if ext == ".csv" else "AQI",
            "status": "pending",
            "input_rows": 0,
            "retained_rows": 0,
            "inserted_rows": 0,
            "error_msg": None
        }

        try:
            # 1. Transform
            if ext == ".csv":
                df, stats = process_caaqms_csv(path)
                file_record["input_rows"] = stats.get("total_rows", 0)
            elif ext == ".xlsx":
                df, stats = process_aqi_xlsx(path)
                file_record["input_rows"] = stats.get("total_rows", 0)
            else:
                continue

            if stats.get("status") == "error":
                raise RuntimeError(f"Transform failure: {stats.get('error')}")

            retained = len(df)
            file_record["retained_rows"] = retained
            print(f"  Transform success. Retained {retained} valid rows.")

            # 2. Database Metadata
            station_id = get_or_create_station(conn, station_name, station_folder, city, operator)

            min_ts = df["ts"].min() if not df.empty else None
            max_ts = df["ts"].max() if not df.empty else None

            source_file_id = get_or_create_source_file(
                conn, station_id, filename, str(path), file_record["type"],
                ext[1:].upper(), min_ts, max_ts, retained
            )

            # 3. Facts Push
            if retained > 0:
                if ext == ".csv":
                    res = insert_caaqms_batch(conn, df, station_id, source_file_id)
                else:
                    res = insert_aqi_batch(conn, df, station_id, source_file_id)
                file_record["inserted_rows"] = res["attempted"]
            else:
                file_record["inserted_rows"] = 0

            # Commit file
            conn.commit()
            file_record["status"] = "success"
            print(f"  Commit success: {file_record['inserted_rows']} rows attempted via execute_values.")

        except Exception as e:
            conn.rollback()
            err_str = str(e)
            file_record["status"] = "failed"
            file_record["error_msg"] = err_str
            stats_report.append(file_record)

            print(f"\n[CRITICAL ERROR] Failed processing {filename}")
            print(f"Error message: {err_str}")
            print("Rolling back and halting production load to preserve integrity.")

            # Save manifest so far
            with open(PROJECT_DIR / "full_load_report.json", "w") as f:
                json.dump(stats_report, f, indent=2)

            sys.exit(1)

        stats_report.append(file_record)

    conn.close()

    # Save complete manifest
    with open(PROJECT_DIR / "full_load_report.json", "w") as f:
        json.dump(stats_report, f, indent=2)

    print("\n=== FULL PRODUCTION ETL LOAD COMPLETED SUCCESSFULLY ===")
    print(f"Processed {len(stats_report)} files.")

if __name__ == "__main__":
    main()

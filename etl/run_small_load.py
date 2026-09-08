"""
run_small_load.py

Thin entry-point to execute the controlled production ETL load for Anand Vihar, Jan 2025.
Runs load_postgres.py's run_small_load() function.
"""

from __future__ import annotations
import json
from load_postgres import run_small_load

if __name__ == "__main__":
    print("=== STARTING SMALL ETL LOAD ===")
    print("Scope: Anand Vihar, January 2025")
    print("Engine: PostgreSQL (psycopg2)")
    print("--------------------------------")

    try:
        results = run_small_load(
            station_folder="Anand Vihar, Delhi - DPCC",
            caaqms_year=2025,
            filter_month=1,
            aqi_month_pattern="January",
            dry_run=False
        )

        print("\n=== LOAD SUCCESSFUL ===")
        print(json.dumps({
            "stations": results["post_counts"]["stations"],
            "source_files": results["post_counts"]["source_files"],
            "caaqms_rows_attempted": results["caaqms_rows_attempted"],
            "aqi_rows_attempted": results["aqi_rows_attempted"],
            "caaqms_total_db_rows": results["post_counts"]["caaqms_hourly"],
            "aqi_total_db_rows": results["post_counts"]["aqi_hourly"],
        }, indent=2))
        print("=======================\n")

    except Exception as e:
        print(f"\n=== LOAD FAILED ===")
        print(f"Error: {e}")
        print("===================\n")
        raise

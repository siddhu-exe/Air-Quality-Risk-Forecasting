"""
verify_full_load.py

Final database validation script to ensure data integrity of the full ETL load.
"""

from __future__ import annotations
import sys
import json
import pandas as pd
from pathlib import Path
from psycopg2.extras import RealDictCursor

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_DIR / "etl"))

from load_postgres import load_env, get_connection

def run_validations():
    env = load_env()
    conn = get_connection(env)

    print("=== SECTION 6: COMPREHENSIVE VALIDATION ===")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # A. Row Counts
        print("\n--- 6.A Row Counts ---")
        cur.execute("SELECT COUNT(*) as c FROM stations")
        print(f"Total stations:      {cur.fetchone()['c']}")
        cur.execute("SELECT COUNT(*) as c FROM source_files")
        print(f"Total source files:  {cur.fetchone()['c']}")
        cur.execute("SELECT COUNT(*) as c FROM caaqms_hourly")
        print(f"Total CAAQMS rows:   {cur.fetchone()['c']}")
        cur.execute("SELECT COUNT(*) as c FROM aqi_hourly")
        print(f"Total AQI rows:      {cur.fetchone()['c']}")

        # Per Station Counts
        print("\nPer-station fact counts:")
        cur.execute("""
            SELECT s.station_name,
                   COUNT(c.timestamp) as caaqms_count
            FROM stations s
            LEFT JOIN caaqms_hourly c ON s.station_id = c.station_id
            GROUP BY s.station_name ORDER BY s.station_name
        """)
        for r in cur.fetchall():
            print(f"  {r['station_name'][:25]:<25}: {r['caaqms_count']:>7} CAAQMS")

        cur.execute("""
            SELECT s.station_name,
                   COUNT(a.timestamp) as aqi_count
            FROM stations s
            LEFT JOIN aqi_hourly a ON s.station_id = a.station_id
            GROUP BY s.station_name ORDER BY s.station_name
        """)
        for r in cur.fetchall():
            if r['aqi_count'] > 0:
                print(f"  {r['station_name'][:25]:<25}: {r['aqi_count']:>7} AQI")

        # C. Time Coverage
        print("\n--- 6.C Time Coverage by Station ---")
        cur.execute("""
            SELECT s.station_name,
                   MIN(c.timestamp) as min_ts,
                   MAX(c.timestamp) as max_ts,
                   COUNT(c.timestamp) as obs_count
            FROM stations s
            JOIN caaqms_hourly c ON s.station_id = c.station_id
            GROUP BY s.station_name ORDER BY s.station_name
        """)
        for r in cur.fetchall():
            expected = 0
            missing = 0
            if r['min_ts'] and r['max_ts']:
                delta = r['max_ts'] - r['min_ts']
                # Delta is a timedelta. Get total seconds / 3600 + 1 for expected hours
                expected = int(delta.total_seconds() / 3600) + 1
                missing = expected - r['obs_count']

            print(f"\n{r['station_name']}")
            print(f"  Range:    {r['min_ts']} to {r['max_ts']}")
            print(f"  Observed: {r['obs_count']} | Expected: {expected} | Gap: {missing} hours")

        # D. Duplicate Checks
        print("\n--- 6.D Duplicate Integrity Check ---")
        cur.execute("SELECT station_id, timestamp, COUNT(*) as c FROM caaqms_hourly GROUP BY station_id, timestamp HAVING COUNT(*) > 1")
        caaqms_dups = cur.fetchall()
        print(f"CAAQMS Duplicates: {len(caaqms_dups)}")

        cur.execute("SELECT station_id, timestamp, COUNT(*) as c FROM aqi_hourly GROUP BY station_id, timestamp HAVING COUNT(*) > 1")
        aqi_dups = cur.fetchall()
        print(f"AQI Duplicates:    {len(aqi_dups)}")

if __name__ == "__main__":
    run_validations()

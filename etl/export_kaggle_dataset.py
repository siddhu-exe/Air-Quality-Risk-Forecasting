"""
Export curated data from PostgreSQL to clean, sanitized public CSVs in kaggle/ directory.
Strictly strips internal filesystem paths, database credentials, and internal surrogate IDs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

KAGGLE_DIR = PROJECT_DIR / "kaggle"
KAGGLE_DIR.mkdir(parents=True, exist_ok=True)

import psycopg2
import pandas as pd
from etl.load_postgres import load_env, get_connection


def export_stations(conn) -> pd.DataFrame:
    print("Exporting stations.csv...")
    query = """
        SELECT
            station_id,
            station_name,
            city,
            operator,
            latitude,
            longitude
        FROM stations
        ORDER BY station_id;
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]

    df = pd.DataFrame(rows, columns=cols)
    out_path = KAGGLE_DIR / "stations.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"  -> Saved {len(df)} rows to {out_path}")
    return df


def export_source_files(conn) -> pd.DataFrame:
    print("Exporting source_files.csv (sanitizing paths)...")
    query = """
        SELECT
            source_file_id,
            station_id,
            filename,
            source_type,
            file_format,
            reporting_period_start,
            reporting_period_end,
            row_count,
            processing_status
        FROM source_files
        ORDER BY source_file_id;
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]

    df = pd.DataFrame(rows, columns=cols)

    # Format timestamps consistently as ISO strings with timezone
    if "reporting_period_start" in df.columns:
        df["reporting_period_start"] = df["reporting_period_start"].apply(
            lambda x: x.isoformat() if pd.notnull(x) else ""
        )
    if "reporting_period_end" in df.columns:
        df["reporting_period_end"] = df["reporting_period_end"].apply(
            lambda x: x.isoformat() if pd.notnull(x) else ""
        )

    out_path = KAGGLE_DIR / "source_files.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"  -> Saved {len(df)} rows to {out_path}")
    return df


def export_caaqms_hourly(conn) -> int:
    print("Exporting caaqms_hourly.csv (162,096 rows)...")
    cols = [
        "station_id", "source_file_id", "timestamp",
        "pm25", "pm10", "no", "no2", "nox", "nh3", "so2", "co", "o3",
        "benzene", "toluene", "xylene", "temperature", "humidity",
        "wind_speed", "wind_direction", "rainfall", "solar_radiation",
        "barometric_pressure", "vertical_wind_speed", "qc_flags"
    ]
    query = f"""
        SELECT {', '.join(cols)}
        FROM caaqms_hourly
        ORDER BY timestamp, station_id;
    """
    out_path = KAGGLE_DIR / "caaqms_hourly.csv"

    with conn.cursor(name="caaqms_cursor") as cur:
        cur.itersize = 10000
        cur.execute(query)

        first_chunk = True
        total_rows = 0

        while True:
            rows = cur.fetchmany(10000)
            if not rows:
                break

            # Process rows
            processed_rows = []
            for r in rows:
                r_list = list(r)
                # Format timestamp
                if r_list[2] is not None:
                    r_list[2] = r_list[2].isoformat()
                # Format qc_flags json
                if r_list[-1] is not None:
                    r_list[-1] = json.dumps(r_list[-1]) if isinstance(r_list[-1], dict) else str(r_list[-1])
                else:
                    r_list[-1] = ""
                processed_rows.append(r_list)

            chunk_df = pd.DataFrame(processed_rows, columns=cols)
            chunk_df.to_csv(
                out_path,
                mode="w" if first_chunk else "a",
                header=first_chunk,
                index=False,
                encoding="utf-8"
            )
            first_chunk = False
            total_rows += len(chunk_df)
            print(f"    Exported {total_rows:,} rows...", end="\r")

    print(f"\n  -> Saved {total_rows:,} rows to {out_path}")
    return total_rows


def export_aqi_hourly(conn) -> int:
    print("Exporting aqi_hourly.csv (57,946 rows)...")
    cols = ["station_id", "source_file_id", "timestamp", "aqi_value", "qc_flags"]
    query = f"""
        SELECT {', '.join(cols)}
        FROM aqi_hourly
        ORDER BY timestamp, station_id;
    """
    out_path = KAGGLE_DIR / "aqi_hourly.csv"

    with conn.cursor(name="aqi_cursor") as cur:
        cur.itersize = 10000
        cur.execute(query)

        first_chunk = True
        total_rows = 0

        while True:
            rows = cur.fetchmany(10000)
            if not rows:
                break

            processed_rows = []
            for r in rows:
                r_list = list(r)
                if r_list[2] is not None:
                    r_list[2] = r_list[2].isoformat()
                if r_list[-1] is not None:
                    r_list[-1] = json.dumps(r_list[-1]) if isinstance(r_list[-1], dict) else str(r_list[-1])
                else:
                    r_list[-1] = ""
                processed_rows.append(r_list)

            chunk_df = pd.DataFrame(processed_rows, columns=cols)
            chunk_df.to_csv(
                out_path,
                mode="w" if first_chunk else "a",
                header=first_chunk,
                index=False,
                encoding="utf-8"
            )
            first_chunk = False
            total_rows += len(chunk_df)
            print(f"    Exported {total_rows:,} rows...", end="\r")

    print(f"\n  -> Saved {total_rows:,} rows to {out_path}")
    return total_rows


def export_column_metadata() -> pd.DataFrame:
    print("Exporting column_metadata.csv...")
    metadata = [
        # stations.csv
        {"file": "stations.csv", "column": "station_id", "description": "Unique integer identifier for the monitoring station", "unit": "dimensionless", "data_type": "integer"},
        {"file": "stations.csv", "column": "station_name", "description": "Official name of the continuous air quality monitoring station", "unit": "string", "data_type": "string"},
        {"file": "stations.csv", "column": "city", "description": "City of station location (Delhi)", "unit": "string", "data_type": "string"},
        {"file": "stations.csv", "column": "operator", "description": "Operating authority (DPCC - Delhi Pollution Control Committee, CPCB - Central Pollution Control Board)", "unit": "string", "data_type": "string"},
        {"file": "stations.csv", "column": "latitude", "description": "Geographic latitude of station (if provided in official records)", "unit": "degrees_north", "data_type": "float"},
        {"file": "stations.csv", "column": "longitude", "description": "Geographic longitude of station (if provided in official records)", "unit": "degrees_east", "data_type": "float"},

        # source_files.csv
        {"file": "source_files.csv", "column": "source_file_id", "description": "Unique integer identifier for raw government telemetry batch", "unit": "dimensionless", "data_type": "integer"},
        {"file": "source_files.csv", "column": "station_id", "description": "Foreign key reference to monitoring station in stations.csv", "unit": "dimensionless", "data_type": "integer"},
        {"file": "source_files.csv", "column": "filename", "description": "Standardized source filename of original government telemetry report", "unit": "string", "data_type": "string"},
        {"file": "source_files.csv", "column": "source_type", "description": "Category of telemetry data (CAAQMS raw telemetry vs AQI calculated index)", "unit": "string", "data_type": "string"},
        {"file": "source_files.csv", "column": "file_format", "description": "File format of source archive (CSV or XLSX)", "unit": "string", "data_type": "string"},
        {"file": "source_files.csv", "column": "reporting_period_start", "description": "Start timestamp of the file reporting window (ISO 8601 UTC)", "unit": "ISO 8601 datetime", "data_type": "datetime"},
        {"file": "source_files.csv", "column": "reporting_period_end", "description": "End timestamp of the file reporting window (ISO 8601 UTC)", "unit": "ISO 8601 datetime", "data_type": "datetime"},
        {"file": "source_files.csv", "column": "row_count", "description": "Total observation rows loaded from this source batch", "unit": "count", "data_type": "integer"},
        {"file": "source_files.csv", "column": "processing_status", "description": "Database ingestion and ETL status (loaded)", "unit": "string", "data_type": "string"},

        # caaqms_hourly.csv
        {"file": "caaqms_hourly.csv", "column": "station_id", "description": "Foreign key identifier referencing stations.csv", "unit": "dimensionless", "data_type": "integer"},
        {"file": "caaqms_hourly.csv", "column": "source_file_id", "description": "Foreign key identifier referencing source_files.csv for data lineage", "unit": "dimensionless", "data_type": "integer"},
        {"file": "caaqms_hourly.csv", "column": "timestamp", "description": "Observation hourly timestamp (ISO 8601 with Asia/Kolkata +05:30 offset)", "unit": "ISO 8601 datetime", "data_type": "datetime"},
        {"file": "caaqms_hourly.csv", "column": "pm25", "description": "Fine particulate matter with aerodynamic diameter <= 2.5 micrometers", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "pm10", "description": "Coarse particulate matter with aerodynamic diameter <= 10 micrometers", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "no", "description": "Nitric oxide concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "no2", "description": "Nitrogen dioxide concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "nox", "description": "Total oxides of nitrogen concentration", "unit": "ppb", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "nh3", "description": "Ammonia concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "so2", "description": "Sulfur dioxide concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "co", "description": "Carbon monoxide concentration", "unit": "mg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "o3", "description": "Ground-level ozone concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "benzene", "description": "Benzene volatile organic compound concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "toluene", "description": "Toluene volatile organic compound concentration", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "xylene", "description": "Xylene volatile organic compound concentration (unpopulated in CPCB sensors)", "unit": "µg/m³", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "temperature", "description": "Ambient air temperature", "unit": "°C", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "humidity", "description": "Relative humidity", "unit": "%", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "wind_speed", "description": "Horizontal wind speed", "unit": "m/s", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "wind_direction", "description": "Wind direction in compass degrees (0-360°)", "unit": "degrees", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "rainfall", "description": "Precipitation recorded during the hour", "unit": "mm", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "solar_radiation", "description": "Global solar irradiance", "unit": "W/m²", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "barometric_pressure", "description": "Atmospheric pressure", "unit": "mmHg", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "vertical_wind_speed", "description": "Vertical wind velocity component", "unit": "m/s", "data_type": "float"},
        {"file": "caaqms_hourly.csv", "column": "qc_flags", "description": "JSON dictionary of non-destructive quality control flags (e.g. out-of-bounds sentinels nullified)", "unit": "JSON string", "data_type": "string"},

        # aqi_hourly.csv
        {"file": "aqi_hourly.csv", "column": "station_id", "description": "Foreign key identifier referencing stations.csv", "unit": "dimensionless", "data_type": "integer"},
        {"file": "aqi_hourly.csv", "column": "source_file_id", "description": "Foreign key identifier referencing source_files.csv for data lineage", "unit": "dimensionless", "data_type": "integer"},
        {"file": "aqi_hourly.csv", "column": "timestamp", "description": "Reporting hourly timestamp (ISO 8601 with Asia/Kolkata +05:30 offset)", "unit": "ISO 8601 datetime", "data_type": "datetime"},
        {"file": "aqi_hourly.csv", "column": "aqi_value", "description": "Official CPCB calculated Air Quality Index (0-500 scale)", "unit": "AQI index points", "data_type": "float"},
        {"file": "aqi_hourly.csv", "column": "qc_flags", "description": "JSON dictionary of quality control flags if applicable", "unit": "JSON string", "data_type": "string"}
    ]

    df = pd.DataFrame(metadata)
    out_path = KAGGLE_DIR / "column_metadata.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"  -> Saved {len(df)} metadata definitions to {out_path}")
    return df


def main():
    env = load_env()
    conn = get_connection(env)

    try:
        export_stations(conn)
        export_source_files(conn)
        export_caaqms_hourly(conn)
        export_aqi_hourly(conn)
        export_column_metadata()
        print("\nAll Kaggle dataset files exported successfully!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

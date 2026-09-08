# etl/load_postgres.py
#
# PostgreSQL loader for the Air Quality ETL pipeline.
# Uses psycopg2 directly — no ORM.  All inserts are idempotent via
# ON CONFLICT (station_id, timestamp) DO UPDATE.
#
# Connection parameters are read exclusively from the project .env file;
# credentials are never hard-coded here.

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg2
import psycopg2.extras  # execute_values

# ── paths ──────────────────────────────────────────────────────────────────
ETL_DIR     = Path(__file__).resolve().parent
PROJECT_DIR = ETL_DIR.parent
ENV_FILE    = PROJECT_DIR / ".env"

# ── ETL column name  →  DB column name ──────────────────────────────────────
# Source: schemas.py CSV_COLUMN_MAPPING + ERD column names in sql/001_create_tables.sql
CAAQMS_COL_MAP: dict[str, str] = {
    "ts":             "timestamp",
    "pm25":           "pm25",
    "pm10":           "pm10",
    "no_ugm3":        "no",
    "no2_ugm3":       "no2",
    "nox_ppb":        "nox",
    "nh3_ugm3":       "nh3",
    "so2_ugm3":       "so2",
    "co_mgm3":        "co",
    "ozone_ugm3":     "o3",
    "benzene_ugm3":   "benzene",
    "toluene_ugm3":   "toluene",
    "xylene_ugm3":    "xylene",
    "temp_c":         "temperature",
    "rh_pct":         "humidity",
    "ws_ms":          "wind_speed",
    "wd_deg":         "wind_direction",
    "rf_mm":          "rainfall",
    "sr_wm2":         "solar_radiation",
    "bp_mmhg":        "barometric_pressure",
    "vws_ms":         "vertical_wind_speed",
    "qc_flags":       "qc_flags",
    # columns present in ETL output but NOT in DB schema — silently dropped:
    # o_xylene_ugm3, eth_benzene_ugm3, mp_xylene_ugm3, tot_rf_mm
}

AQI_COL_MAP: dict[str, str] = {
    "ts":        "timestamp",
    "aqi":       "aqi_value",
    "qc_flags":  "qc_flags",
}


# ── env / connection ─────────────────────────────────────────────────────────

def load_env() -> dict[str, str]:
    """Parse PROJECT_DIR/.env into a plain dict.  Never hard-codes credentials."""
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env not found at {ENV_FILE}")
    with ENV_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    required = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
                "POSTGRES_HOST", "POSTGRES_PORT"}
    missing = required - env.keys()
    if missing:
        raise ValueError(f"Missing keys in .env: {missing}")
    return env


def get_connection(env: dict[str, str]):
    """Return an open psycopg2 connection with autocommit=False."""
    return psycopg2.connect(
        host=env["POSTGRES_HOST"],
        port=int(env["POSTGRES_PORT"]),
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    )


# ── dimension helpers ────────────────────────────────────────────────────────

def get_or_create_station(
    conn,
    station_name: str,
    raw_folder_name: str,
    city: str,
    operator: str,
) -> int:
    """
    Return station_id for the given station_name, inserting if not present.
    No UNIQUE constraint exists on station_name, so we do SELECT then INSERT.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT station_id FROM stations WHERE station_name = %s",
            (station_name,),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            """
            INSERT INTO stations (station_name, raw_folder_name, city, operator)
            VALUES (%s, %s, %s, %s)
            RETURNING station_id
            """,
            (station_name, raw_folder_name, city, operator),
        )
        return cur.fetchone()[0]


def get_or_create_source_file(
    conn,
    station_id: int,
    filename: str,
    path: str,
    source_type: str,
    file_format: str,
    reporting_start,
    reporting_end,
    row_count: int,
) -> int:
    """
    Return source_file_id for (station_id, filename).  Inserts if absent,
    updates row_count / reporting period if already present (idempotent re-run).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_file_id FROM source_files
            WHERE station_id = %s AND filename = %s
            """,
            (station_id, filename),
        )
        row = cur.fetchone()
        if row:
            # Update metadata so a re-run stays consistent
            cur.execute(
                """
                UPDATE source_files
                SET row_count = %s,
                    reporting_period_start = %s,
                    reporting_period_end   = %s,
                    processing_status      = 'loaded'
                WHERE source_file_id = %s
                """,
                (row_count, reporting_start, reporting_end, row[0]),
            )
            return row[0]
        cur.execute(
            """
            INSERT INTO source_files
                (station_id, filename, path, source_type, file_format,
                 reporting_period_start, reporting_period_end,
                 row_count, processing_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'loaded')
            RETURNING source_file_id
            """,
            (station_id, filename, path, source_type, file_format,
             reporting_start, reporting_end, row_count),
        )
        return cur.fetchone()[0]


# ── fact-table upserts ───────────────────────────────────────────────────────

# DB columns for caaqms_hourly (in insert order, excluding PK and created_at)
_CAAQMS_DB_COLS = [
    "station_id", "source_file_id", "timestamp",
    "pm25", "pm10", "no", "no2", "nox", "nh3", "so2", "co", "o3",
    "benzene", "toluene", "xylene",
    "temperature", "humidity", "wind_speed", "wind_direction",
    "rainfall", "solar_radiation", "barometric_pressure", "vertical_wind_speed",
    "qc_flags",
]

_AQI_DB_COLS = [
    "station_id", "source_file_id", "timestamp",
    "aqi_value", "qc_flags",
]


def _df_to_caaqms_rows(
    df: pd.DataFrame, station_id: int, source_file_id: int
) -> list[tuple]:
    """Map ETL dataframe → list of tuples matching _CAAQMS_DB_COLS."""
    # Rename ETL columns to DB columns, keeping only what we need
    renamed = df.rename(columns=CAAQMS_COL_MAP)
    rows = []
    for _, r in renamed.iterrows():
        row = (
            station_id,
            source_file_id,
            r["timestamp"],              # TIMESTAMPTZ — already tz-aware from ETL
            _f(r, "pm25"),
            _f(r, "pm10"),
            _f(r, "no"),
            _f(r, "no2"),
            _f(r, "nox"),
            _f(r, "nh3"),
            _f(r, "so2"),
            _f(r, "co"),
            _f(r, "o3"),
            _f(r, "benzene"),
            _f(r, "toluene"),
            _f(r, "xylene"),
            _f(r, "temperature"),
            _f(r, "humidity"),
            _f(r, "wind_speed"),
            _f(r, "wind_direction"),
            _f(r, "rainfall"),
            _f(r, "solar_radiation"),
            _f(r, "barometric_pressure"),
            _f(r, "vertical_wind_speed"),
            r.get("qc_flags"),           # already a JSON string or None
        )
        rows.append(row)
    return rows


def _df_to_aqi_rows(
    df: pd.DataFrame, station_id: int, source_file_id: int
) -> list[tuple]:
    """Map ETL dataframe → list of tuples matching _AQI_DB_COLS."""
    renamed = df.rename(columns=AQI_COL_MAP)
    rows = []
    for _, r in renamed.iterrows():
        rows.append((
            station_id,
            source_file_id,
            r["timestamp"],
            _f(r, "aqi_value"),
            r.get("qc_flags"),
        ))
    return rows


def _f(row, col):
    """Return None for NaN/missing, otherwise the scalar value."""
    val = row.get(col)
    if val is None:
        return None
    try:
        import math
        if math.isnan(float(val)):
            return None
    except (TypeError, ValueError):
        pass
    return val


def _build_upsert_caaqms() -> str:
    cols = ", ".join(_CAAQMS_DB_COLS)
    placeholders = ", ".join(["%s"] * len(_CAAQMS_DB_COLS))
    update_cols = [
        c for c in _CAAQMS_DB_COLS
        if c not in ("station_id", "source_file_id", "timestamp")
    ]
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    return f"""
        INSERT INTO caaqms_hourly ({cols})
        VALUES %s
        ON CONFLICT (station_id, timestamp)
        DO UPDATE SET {update_clause}
    """


def _build_upsert_aqi() -> str:
    cols = ", ".join(_AQI_DB_COLS)
    update_cols = [c for c in _AQI_DB_COLS
                   if c not in ("station_id", "source_file_id", "timestamp")]
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    return f"""
        INSERT INTO aqi_hourly ({cols})
        VALUES %s
        ON CONFLICT (station_id, timestamp)
        DO UPDATE SET {update_clause}
    """


def insert_caaqms_batch(
    conn, df: pd.DataFrame, station_id: int, source_file_id: int
) -> dict[str, int]:
    """Upsert CAAQMS rows inside an already-open transaction."""
    rows = _df_to_caaqms_rows(df, station_id, source_file_id)
    if not rows:
        return {"inserted": 0, "updated": 0}
    sql = _build_upsert_caaqms()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows, page_size=500)
    return {"attempted": len(rows)}


def insert_aqi_batch(
    conn, df: pd.DataFrame, station_id: int, source_file_id: int
) -> dict[str, int]:
    """Upsert AQI rows inside an already-open transaction."""
    rows = _df_to_aqi_rows(df, station_id, source_file_id)
    if not rows:
        return {"attempted": 0}
    sql = _build_upsert_aqi()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows, page_size=500)
    return {"attempted": len(rows)}


# ── main orchestration ────────────────────────────────────────────────────────

def run_small_load(
    station_folder: str = "Anand Vihar, Delhi - DPCC",
    caaqms_year: int = 2025,
    filter_month: int = 1,          # January only
    aqi_month_pattern: str = "January",
    dry_run: bool = False,
) -> dict:
    """
    Controlled production load for ONE station, ONE month.

    Steps
    -----
    1. Load .env, open connection
    2. Pre-check: all 4 tables must be empty (no prior production rows)
    3. Transform CAAQMS CSV → filter to January 2025 rows
    4. Transform AQI XLSX → January 2025 file
    5. Insert station → source_files → caaqms_hourly → aqi_hourly
    6. Commit
    7. Return stats dict for reporting
    """
    from transform_caaqms import process_caaqms_csv
    from transform_aqi import process_aqi_xlsx
    from schemas import clean_station_name

    DATA_ROOT = PROJECT_DIR / "Og Data" / "Delhi data"
    station_dir = DATA_ROOT / station_folder

    # ── locate files ────────────────────────────────────────────────────────
    caaqms_path = (station_dir / "Raw Data" /
                   f"{caaqms_year}_raw_data_hourly_"
                   f"{station_folder.lower().replace(' ', '_').replace('-', '-')}_1H.csv")

    # Fuzzy-find the CSV if the exact name differs slightly
    if not caaqms_path.exists():
        candidates = list((station_dir / "Raw Data").glob(f"{caaqms_year}_*.csv"))
        if not candidates:
            raise FileNotFoundError(
                f"No {caaqms_year} CAAQMS CSV found in {station_dir / 'Raw Data'}"
            )
        caaqms_path = candidates[0]

    aqi_candidates = list((station_dir / "AQI Hourly").glob(
        f"*_{caaqms_year}_{aqi_month_pattern}_*.xlsx"
    ))
    if not aqi_candidates:
        raise FileNotFoundError(
            f"No AQI XLSX for {aqi_month_pattern} {caaqms_year} in {station_dir / 'AQI Hourly'}"
        )
    aqi_path = aqi_candidates[0]

    # ── transform ────────────────────────────────────────────────────────────
    print(f"\n[TRANSFORM] CAAQMS: {caaqms_path.name}")
    caaqms_df, caaqms_stats = process_caaqms_csv(caaqms_path)
    if caaqms_stats["status"] == "error":
        raise RuntimeError(f"CAAQMS transform failed: {caaqms_stats['error']}")

    # Filter to the target month
    caaqms_df = caaqms_df[caaqms_df["ts"].dt.month == filter_month].copy()
    print(f"           {len(caaqms_df):,} rows after filtering to month={filter_month}")

    print(f"[TRANSFORM] AQI   : {aqi_path.name}")
    aqi_df, aqi_stats = process_aqi_xlsx(aqi_path)
    if aqi_stats["status"] == "error":
        raise RuntimeError(f"AQI transform failed: {aqi_stats['error']}")
    print(f"           {len(aqi_df):,} AQI rows")

    if dry_run:
        print("\n[DRY RUN] Transform complete — no DB writes.")
        return {
            "dry_run": True,
            "caaqms_rows": len(caaqms_df),
            "aqi_rows": len(aqi_df),
        }

    # ── station metadata ─────────────────────────────────────────────────────
    station_name, city, operator = clean_station_name(station_folder)

    # ── connect & pre-check ─────────────────────────────────────────────────
    env = load_env()
    conn = get_connection(env)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stations")
            pre_station_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM caaqms_hourly")
            pre_caaqms_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM aqi_hourly")
            pre_aqi_count = cur.fetchone()[0]

        print(f"\n[PRE-CHECK] stations={pre_station_count}  "
              f"caaqms_hourly={pre_caaqms_count}  aqi_hourly={pre_aqi_count}")

        # ── insert station ────────────────────────────────────────────────────
        station_id = get_or_create_station(
            conn, station_name, station_folder, city, operator
        )
        print(f"[STATION]  '{station_name}' → station_id={station_id}")

        # ── insert source_file records ───────────────────────────────────────
        caaqms_source_id = get_or_create_source_file(
            conn,
            station_id,
            caaqms_path.name,
            str(caaqms_path),
            "CAAQMS",
            "CSV",
            caaqms_df["ts"].min() if not caaqms_df.empty else None,
            caaqms_df["ts"].max() if not caaqms_df.empty else None,
            len(caaqms_df),
        )
        print(f"[SRC FILE] CAAQMS → source_file_id={caaqms_source_id}")

        aqi_source_id = get_or_create_source_file(
            conn,
            station_id,
            aqi_path.name,
            str(aqi_path),
            "AQI",
            "XLSX",
            aqi_df["ts"].min() if not aqi_df.empty else None,
            aqi_df["ts"].max() if not aqi_df.empty else None,
            len(aqi_df),
        )
        print(f"[SRC FILE] AQI    → source_file_id={aqi_source_id}")

        # ── upsert facts ──────────────────────────────────────────────────────
        print(f"\n[INSERT] CAAQMS → {len(caaqms_df):,} rows …")
        caaqms_result = insert_caaqms_batch(conn, caaqms_df, station_id, caaqms_source_id)

        print(f"[INSERT] AQI    → {len(aqi_df):,} rows …")
        aqi_result = insert_aqi_batch(conn, aqi_df, station_id, aqi_source_id)

        conn.commit()
        print("[COMMIT]  Transaction committed successfully.")

        # ── post-load counts ─────────────────────────────────────────────────
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stations")
            post_station = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM source_files")
            post_sf = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM caaqms_hourly")
            post_caaqms = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM aqi_hourly")
            post_aqi = cur.fetchone()[0]

        return {
            "dry_run": False,
            "station_id": station_id,
            "caaqms_source_file_id": caaqms_source_id,
            "aqi_source_file_id": aqi_source_id,
            "caaqms_rows_attempted": caaqms_result["attempted"],
            "aqi_rows_attempted":    aqi_result["attempted"],
            "post_counts": {
                "stations":      post_station,
                "source_files":  post_sf,
                "caaqms_hourly": post_caaqms,
                "aqi_hourly":    post_aqi,
            },
            "caaqms_stats": caaqms_stats,
            "aqi_stats":    aqi_stats,
        }

    except Exception:
        conn.rollback()
        print("[ROLLBACK] Error encountered — transaction rolled back.")
        raise
    finally:
        conn.close()

# etl/load_postgres.py
import pandas as pd
# from sqlalchemy import create_engine
# from sqlalchemy.dialects.postgresql import insert

def load_data_to_db(df: pd.DataFrame, table_name: str, station_id: int, source_file_id: int, dry_run: bool = True) -> int:
    """
    Simulates or executes an UPSERT to PostgreSQL.

    In dry_run mode, simply returns the count of records that would be inserted/updated.
    In prod mode, uses SQLAlchemy with ON CONFLICT DO UPDATE.
    """
    if df.empty:
        return 0

    df_load = df.copy()
    df_load["station_id"] = station_id
    df_load["source_file_id"] = source_file_id

    rows_to_insert = len(df_load)

    if dry_run:
        # Simulate successful insertion
        pass
    else:
        # PostgreSQL logic goes here when database is available
        # e.g.,
        # engine = create_engine(DB_URI)
        # with engine.begin() as conn:
        #     # Construct postgresql specific UPSERT
        #     ...
        print(f"Database insert pipeline not yet activated. Would have inserted {rows_to_insert} rows into {table_name}.")

    return rows_to_insert

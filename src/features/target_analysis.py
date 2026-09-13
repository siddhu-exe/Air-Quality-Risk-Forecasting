"""
target_analysis.py
Calculates target availability for future AQI horizons (1h, 6h, 24h)
across stations, years, and months from PostgreSQL air_quality_db.
"""

import os
import pandas as pd
import psycopg2
from pathlib import Path

# DB Connection settings
DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": os.getenv("POSTGRES_PORT", "5433"),
    "dbname": os.getenv("POSTGRES_DB", "air_quality_db"),
    "user": os.getenv("POSTGRES_USER", "aq_admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "aq_password_2025"),
}

OUTPUT_DIR = Path("reports/features")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def analyze_target_availability():
    conn = psycopg2.connect(**DB_PARAMS)

    # Query all aqi_hourly timestamps per station
    query = """
    SELECT
        s.station_name,
        a.station_id,
        a.timestamp,
        a.aqi_value
    FROM aqi_hourly a
    JOIN stations s ON a.station_id = s.station_id
    ORDER BY a.station_id, a.timestamp;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"Loaded {len(df)} total AQI records across {df['station_name'].nunique()} stations.")

    # Ensure timezone is converted to Asia/Kolkata
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('Asia/Kolkata')

    records = []

    for station_name, group in df.groupby('station_name'):
        group = group.sort_values('timestamp').set_index('timestamp')

        # Create full continuous hourly range for 2025 in Asia/Kolkata
        min_ts = pd.Timestamp("2025-01-01 00:00:00", tz='Asia/Kolkata')
        max_ts = pd.Timestamp("2025-12-31 23:00:00", tz='Asia/Kolkata')
        full_idx = pd.date_range(min_ts, max_ts, freq='h', tz='Asia/Kolkata')

        reindexed = group.reindex(full_idx)
        reindexed['station_name'] = station_name
        reindexed['station_id'] = group['station_id'].iloc[0]

        # Calculate targets for horizons 1h, 6h, 24h
        reindexed['target_1h'] = reindexed['aqi_value'].shift(-1)
        reindexed['target_6h'] = reindexed['aqi_value'].shift(-6)
        reindexed['target_24h'] = reindexed['aqi_value'].shift(-24)

        # Filter to rows where current aqi_value exists
        has_current = reindexed.dropna(subset=['aqi_value']).copy()
        has_current['year'] = has_current.index.year
        has_current['month'] = has_current.index.month

        # Aggregate by month
        for (yr, mo), mo_grp in has_current.groupby(['year', 'month']):
            total_obs = len(mo_grp)
            avail_1h = int(mo_grp['target_1h'].notna().sum())
            avail_6h = int(mo_grp['target_6h'].notna().sum())
            avail_24h = int(mo_grp['target_24h'].notna().sum())

            records.append({
                "station_name": station_name,
                "year": int(yr),
                "month": int(mo),
                "current_aqi_obs": total_obs,
                "avail_target_1h": avail_1h,
                "pct_target_1h": round(avail_1h / total_obs * 100, 2),
                "avail_target_6h": avail_6h,
                "pct_target_6h": round(avail_6h / total_obs * 100, 2),
                "avail_target_24h": avail_24h,
                "pct_target_24h": round(avail_24h / total_obs * 100, 2),
            })

    summary_df = pd.DataFrame(records)
    summary_df.to_csv(OUTPUT_DIR / "target_availability_monthly.csv", index=False)

    # Overall summary per station
    station_summary = summary_df.groupby("station_name").agg({
        "current_aqi_obs": "sum",
        "avail_target_1h": "sum",
        "avail_target_6h": "sum",
        "avail_target_24h": "sum"
    }).reset_index()
    station_summary["pct_1h"] = round(station_summary["avail_target_1h"] / station_summary["current_aqi_obs"] * 100, 2)
    station_summary["pct_6h"] = round(station_summary["avail_target_6h"] / station_summary["current_aqi_obs"] * 100, 2)
    station_summary["pct_24h"] = round(station_summary["avail_target_24h"] / station_summary["current_aqi_obs"] * 100, 2)
    station_summary.to_csv(OUTPUT_DIR / "target_availability_station_summary.csv", index=False)

    print("\n=== Station-Level Target Availability ===")
    print(station_summary[["station_name", "current_aqi_obs", "pct_1h", "pct_6h", "pct_24h"]].to_string(index=False))

    # Horizon comparison across all data
    total_curr = int(station_summary["current_aqi_obs"].sum())
    total_1h = int(station_summary["avail_target_1h"].sum())
    total_6h = int(station_summary["avail_target_6h"].sum())
    total_24h = int(station_summary["avail_target_24h"].sum())

    print("\n=== Network-Wide Horizon Coverage ===")
    print(f"Total Current Observations: {total_curr:,}")
    print(f"1-Hour Ahead Target:  {total_1h:,} ({total_1h/total_curr*100:.2f}%)")
    print(f"6-Hours Ahead Target: {total_6h:,} ({total_6h/total_curr*100:.2f}%)")
    print(f"24-Hours Ahead Target:{total_24h:,} ({total_24h/total_curr*100:.2f}%)")

    # Monthly Network Total
    monthly_agg = summary_df.groupby(["year", "month"]).agg({
        "current_aqi_obs": "sum",
        "avail_target_1h": "sum",
        "avail_target_6h": "sum",
        "avail_target_24h": "sum"
    }).reset_index()
    monthly_agg["pct_1h"] = round(monthly_agg["avail_target_1h"] / monthly_agg["current_aqi_obs"] * 100, 2)
    monthly_agg["pct_6h"] = round(monthly_agg["avail_target_6h"] / monthly_agg["current_aqi_obs"] * 100, 2)
    monthly_agg["pct_24h"] = round(monthly_agg["avail_target_24h"] / monthly_agg["current_aqi_obs"] * 100, 2)
    print("\n=== Network-Wide Monthly Target Availability ===")
    print(monthly_agg.to_string(index=False))

    return summary_df, station_summary, monthly_agg


if __name__ == "__main__":
    analyze_target_availability()

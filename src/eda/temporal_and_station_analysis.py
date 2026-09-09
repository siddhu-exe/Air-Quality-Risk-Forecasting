"""
src/eda/temporal_and_station_analysis.py

Performs Temporal, Seasonal, and Station Comparative Analysis using SQL aggregations.
Generates:
- reports/eda/hourly_summary.csv
- reports/eda/day_of_week_summary.csv
- reports/eda/monthly_summary.csv
- reports/eda/seasonal_summary.csv
- reports/eda/station_summary.csv
- reports/eda/station_seasonal_ranking.csv
"""

from __future__ import annotations
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_DIR / "etl"))

from load_postgres import load_env, get_connection

def run_temporal_and_station_analysis():
    env = load_env()
    conn = get_connection(env)
    reports_dir = PROJECT_DIR / "reports" / "eda"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=== STARTING TEMPORAL, SEASONAL & STATION ANALYSIS ===")

    # 1. Hourly Profile (Diurnal Cycle)
    print("\n1. Calculating Hourly Diurnal Profiles...")
    hourly_query = """
    WITH caaqms_hourly_stats AS (
        SELECT
            s.station_name,
            EXTRACT(HOUR FROM c.timestamp)::int AS hour_of_day,
            COUNT(c.timestamp) AS obs_count,
            AVG(c.pm25) AS pm25_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm25) AS pm25_median,
            AVG(c.pm10) AS pm10_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm10) AS pm10_median,
            AVG(c.no2) AS no2_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.no2) AS no2_median,
            AVG(c.o3) AS o3_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.o3) AS o3_median,
            AVG(c.co) AS co_mean,
            AVG(c.temperature) AS temp_mean,
            AVG(c.humidity) AS humidity_mean,
            AVG(c.wind_speed) AS wind_speed_mean
        FROM caaqms_hourly c
        JOIN stations s ON c.station_id = s.station_id
        GROUP BY s.station_name, hour_of_day
    ),
    aqi_hourly_stats AS (
        SELECT
            s.station_name,
            EXTRACT(HOUR FROM a.timestamp)::int AS hour_of_day,
            AVG(a.aqi_value) AS aqi_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_p90
        FROM aqi_hourly a
        JOIN stations s ON a.station_id = s.station_id
        GROUP BY s.station_name, hour_of_day
    )
    SELECT
        c.station_name,
        c.hour_of_day,
        c.obs_count,
        ROUND(c.pm25_mean::numeric, 2) AS pm25_mean,
        ROUND(c.pm25_median::numeric, 2) AS pm25_median,
        ROUND(c.pm10_mean::numeric, 2) AS pm10_mean,
        ROUND(c.pm10_median::numeric, 2) AS pm10_median,
        ROUND(c.no2_mean::numeric, 2) AS no2_mean,
        ROUND(c.no2_median::numeric, 2) AS no2_median,
        ROUND(c.o3_mean::numeric, 2) AS o3_mean,
        ROUND(c.o3_median::numeric, 2) AS o3_median,
        ROUND(c.co_mean::numeric, 2) AS co_mean,
        ROUND(c.temp_mean::numeric, 2) AS temp_mean,
        ROUND(c.humidity_mean::numeric, 2) AS humidity_mean,
        ROUND(c.wind_speed_mean::numeric, 2) AS wind_speed_mean,
        ROUND(a.aqi_mean::numeric, 2) AS aqi_mean,
        ROUND(a.aqi_median::numeric, 2) AS aqi_median,
        ROUND(a.aqi_p90::numeric, 2) AS aqi_p90
    FROM caaqms_hourly_stats c
    LEFT JOIN aqi_hourly_stats a ON c.station_name = a.station_name AND c.hour_of_day = a.hour_of_day
    ORDER BY c.station_name, c.hour_of_day;
    """
    df_hourly = pd.read_sql_query(hourly_query, conn)
    df_hourly.to_csv(reports_dir / "hourly_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'hourly_summary.csv'}")

    # 2. Day of Week Profile
    print("\n2. Calculating Day of Week Profiles...")
    dow_query = """
    WITH caaqms_dow AS (
        SELECT
            s.station_name,
            EXTRACT(ISODOW FROM c.timestamp)::int AS day_of_week,
            TO_CHAR(c.timestamp, 'Day') AS day_name,
            AVG(c.pm25) AS pm25_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm25) AS pm25_median,
            AVG(c.pm10) AS pm10_mean,
            AVG(c.no2) AS no2_mean,
            AVG(c.o3) AS o3_mean,
            AVG(c.co) AS co_mean
        FROM caaqms_hourly c
        JOIN stations s ON c.station_id = s.station_id
        GROUP BY s.station_name, day_of_week, day_name
    ),
    aqi_dow AS (
        SELECT
            s.station_name,
            EXTRACT(ISODOW FROM a.timestamp)::int AS day_of_week,
            AVG(a.aqi_value) AS aqi_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_median
        FROM aqi_hourly a
        JOIN stations s ON a.station_id = s.station_id
        GROUP BY s.station_name, day_of_week
    )
    SELECT
        c.station_name,
        c.day_of_week,
        TRIM(c.day_name) AS day_name,
        ROUND(c.pm25_mean::numeric, 2) AS pm25_mean,
        ROUND(c.pm25_median::numeric, 2) AS pm25_median,
        ROUND(c.pm10_mean::numeric, 2) AS pm10_mean,
        ROUND(c.no2_mean::numeric, 2) AS no2_mean,
        ROUND(c.o3_mean::numeric, 2) AS o3_mean,
        ROUND(c.co_mean::numeric, 2) AS co_mean,
        ROUND(a.aqi_mean::numeric, 2) AS aqi_mean,
        ROUND(a.aqi_median::numeric, 2) AS aqi_median
    FROM caaqms_dow c
    LEFT JOIN aqi_dow a ON c.station_name = a.station_name AND c.day_of_week = a.day_of_week
    ORDER BY c.station_name, c.day_of_week;
    """
    df_dow = pd.read_sql_query(dow_query, conn)
    df_dow.to_csv(reports_dir / "day_of_week_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'day_of_week_summary.csv'}")

    # 3. Monthly Profile by Station and Year
    print("\n3. Calculating Monthly Profiles...")
    monthly_query = """
    WITH caaqms_m AS (
        SELECT
            s.station_name,
            EXTRACT(YEAR FROM c.timestamp)::int AS year,
            EXTRACT(MONTH FROM c.timestamp)::int AS month,
            COUNT(c.timestamp) AS obs_count,
            AVG(c.pm25) AS pm25_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm25) AS pm25_median,
            AVG(c.pm10) AS pm10_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm10) AS pm10_median,
            AVG(c.no2) AS no2_mean,
            AVG(c.o3) AS o3_mean,
            AVG(c.temperature) AS temp_mean,
            AVG(c.humidity) AS humidity_mean,
            AVG(c.wind_speed) AS wind_speed_mean
        FROM caaqms_hourly c
        JOIN stations s ON c.station_id = s.station_id
        GROUP BY s.station_name, year, month
    ),
    aqi_m AS (
        SELECT
            s.station_name,
            EXTRACT(YEAR FROM a.timestamp)::int AS year,
            EXTRACT(MONTH FROM a.timestamp)::int AS month,
            COUNT(a.timestamp) AS aqi_obs_count,
            AVG(a.aqi_value) AS aqi_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_p90
        FROM aqi_hourly a
        JOIN stations s ON a.station_id = s.station_id
        GROUP BY s.station_name, year, month
    )
    SELECT
        c.station_name,
        c.year,
        c.month,
        TO_CHAR(TO_DATE(c.month::text, 'MM'), 'Mon') AS month_name,
        c.obs_count AS caaqms_obs,
        ROUND(c.pm25_mean::numeric, 2) AS pm25_mean,
        ROUND(c.pm25_median::numeric, 2) AS pm25_median,
        ROUND(c.pm10_mean::numeric, 2) AS pm10_mean,
        ROUND(c.pm10_median::numeric, 2) AS pm10_median,
        ROUND(c.no2_mean::numeric, 2) AS no2_mean,
        ROUND(c.o3_mean::numeric, 2) AS o3_mean,
        ROUND(c.temp_mean::numeric, 2) AS temp_mean,
        ROUND(c.humidity_mean::numeric, 2) AS humidity_mean,
        ROUND(c.wind_speed_mean::numeric, 2) AS wind_speed_mean,
        COALESCE(a.aqi_obs_count, 0) AS aqi_obs,
        ROUND(a.aqi_mean::numeric, 2) AS aqi_mean,
        ROUND(a.aqi_median::numeric, 2) AS aqi_median,
        ROUND(a.aqi_p90::numeric, 2) AS aqi_p90
    FROM caaqms_m c
    LEFT JOIN aqi_m a ON c.station_name = a.station_name AND c.year = a.year AND c.month = a.month
    ORDER BY c.station_name, c.year, c.month;
    """
    df_monthly = pd.read_sql_query(monthly_query, conn)
    df_monthly.to_csv(reports_dir / "monthly_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'monthly_summary.csv'}")

    # 4. Seasonal Analysis
    # Standard meteorological seasons for Delhi:
    # Winter: Dec, Jan, Feb
    # Summer / Pre-Monsoon: Mar, Apr, May
    # Monsoon: Jun, Jul, Aug, Sep
    # Post-Monsoon: Oct, Nov
    print("\n4. Calculating Seasonal Summaries...")
    seasonal_query = """
    WITH caaqms_season AS (
        SELECT
            s.station_name,
            CASE
                WHEN EXTRACT(MONTH FROM c.timestamp) IN (12, 1, 2) THEN 'Winter'
                WHEN EXTRACT(MONTH FROM c.timestamp) IN (3, 4, 5) THEN 'Summer'
                WHEN EXTRACT(MONTH FROM c.timestamp) IN (6, 7, 8, 9) THEN 'Monsoon'
                WHEN EXTRACT(MONTH FROM c.timestamp) IN (10, 11) THEN 'Post-Monsoon'
            END AS season,
            COUNT(c.timestamp) AS obs_count,
            AVG(c.pm25) AS pm25_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm25) AS pm25_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY c.pm25) AS pm25_p90,
            AVG(c.pm10) AS pm10_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm10) AS pm10_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY c.pm10) AS pm10_p90,
            AVG(c.no2) AS no2_mean,
            AVG(c.o3) AS o3_mean,
            AVG(c.temperature) AS temp_mean,
            AVG(c.humidity) AS humidity_mean,
            AVG(c.wind_speed) AS wind_speed_mean
        FROM caaqms_hourly c
        JOIN stations s ON c.station_id = s.station_id
        GROUP BY s.station_name, season
    ),
    aqi_season AS (
        SELECT
            s.station_name,
            CASE
                WHEN EXTRACT(MONTH FROM a.timestamp) IN (12, 1, 2) THEN 'Winter'
                WHEN EXTRACT(MONTH FROM a.timestamp) IN (3, 4, 5) THEN 'Summer'
                WHEN EXTRACT(MONTH FROM a.timestamp) IN (6, 7, 8, 9) THEN 'Monsoon'
                WHEN EXTRACT(MONTH FROM a.timestamp) IN (10, 11) THEN 'Post-Monsoon'
            END AS season,
            COUNT(a.timestamp) AS aqi_obs_count,
            AVG(a.aqi_value) AS aqi_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_p95,
            MAX(a.aqi_value) AS aqi_max
        FROM aqi_hourly a
        JOIN stations s ON a.station_id = s.station_id
        GROUP BY s.station_name, season
    )
    SELECT
        c.station_name,
        c.season,
        c.obs_count AS caaqms_obs,
        ROUND(c.pm25_mean::numeric, 2) AS pm25_mean,
        ROUND(c.pm25_median::numeric, 2) AS pm25_median,
        ROUND(c.pm25_p90::numeric, 2) AS pm25_p90,
        ROUND(c.pm10_mean::numeric, 2) AS pm10_mean,
        ROUND(c.pm10_median::numeric, 2) AS pm10_median,
        ROUND(c.pm10_p90::numeric, 2) AS pm10_p90,
        ROUND(c.no2_mean::numeric, 2) AS no2_mean,
        ROUND(c.o3_mean::numeric, 2) AS o3_mean,
        ROUND(c.temp_mean::numeric, 2) AS temp_mean,
        ROUND(c.humidity_mean::numeric, 2) AS humidity_mean,
        ROUND(c.wind_speed_mean::numeric, 2) AS wind_speed_mean,
        COALESCE(a.aqi_obs_count, 0) AS aqi_obs,
        ROUND(a.aqi_mean::numeric, 2) AS aqi_mean,
        ROUND(a.aqi_median::numeric, 2) AS aqi_median,
        ROUND(a.aqi_p90::numeric, 2) AS aqi_p90,
        ROUND(a.aqi_p95::numeric, 2) AS aqi_p95,
        a.aqi_max
    FROM caaqms_season c
    LEFT JOIN aqi_season a ON c.station_name = a.station_name AND c.season = a.season
    ORDER BY c.station_name,
        CASE c.season
            WHEN 'Winter' THEN 1
            WHEN 'Summer' THEN 2
            WHEN 'Monsoon' THEN 3
            WHEN 'Post-Monsoon' THEN 4
        END;
    """
    df_seasonal = pd.read_sql_query(seasonal_query, conn)
    df_seasonal.to_csv(reports_dir / "seasonal_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'seasonal_summary.csv'}")

    # 5. Station Summary & Multi-Metric Ranking
    print("\n5. Calculating Overall Station Comparison Summary...")
    station_query = """
    WITH st_caaqms AS (
        SELECT
            s.station_name,
            s.operator,
            COUNT(c.timestamp) AS total_caaqms_obs,
            AVG(c.pm25) AS pm25_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm25) AS pm25_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY c.pm25) AS pm25_p90,
            AVG(c.pm10) AS pm10_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.pm10) AS pm10_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY c.pm10) AS pm10_p90,
            AVG(c.no2) AS no2_mean,
            AVG(c.o3) AS o3_mean,
            AVG(c.co) AS co_mean,
            AVG(c.so2) AS so2_mean
        FROM caaqms_hourly c
        JOIN stations s ON c.station_id = s.station_id
        GROUP BY s.station_name, s.operator
    ),
    st_aqi AS (
        SELECT
            s.station_name,
            COUNT(a.timestamp) AS total_aqi_obs,
            AVG(a.aqi_value) AS aqi_mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_median,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.aqi_value) AS aqi_p95,
            MAX(a.aqi_value) AS aqi_max,
            STDDEV(a.aqi_value) AS aqi_std
        FROM aqi_hourly a
        JOIN stations s ON a.station_id = s.station_id
        GROUP BY s.station_name
    )
    SELECT
        c.station_name,
        c.operator,
        c.total_caaqms_obs,
        a.total_aqi_obs,
        ROUND(a.aqi_mean::numeric, 2) AS aqi_mean,
        ROUND(a.aqi_median::numeric, 2) AS aqi_median,
        ROUND(a.aqi_p90::numeric, 2) AS aqi_p90,
        ROUND(a.aqi_p95::numeric, 2) AS aqi_p95,
        a.aqi_max,
        ROUND(a.aqi_std::numeric, 2) AS aqi_std,
        ROUND(c.pm25_mean::numeric, 2) AS pm25_mean,
        ROUND(c.pm25_median::numeric, 2) AS pm25_median,
        ROUND(c.pm25_p90::numeric, 2) AS pm25_p90,
        ROUND(c.pm10_mean::numeric, 2) AS pm10_mean,
        ROUND(c.pm10_median::numeric, 2) AS pm10_median,
        ROUND(c.pm10_p90::numeric, 2) AS pm10_p90,
        ROUND(c.no2_mean::numeric, 2) AS no2_mean,
        ROUND(c.o3_mean::numeric, 2) AS o3_mean,
        ROUND(c.co_mean::numeric, 2) AS co_mean,
        ROUND(c.so2_mean::numeric, 2) AS so2_mean
    FROM st_caaqms c
    JOIN st_aqi a ON c.station_name = a.station_name
    ORDER BY aqi_mean DESC;
    """
    df_station = pd.read_sql_query(station_query, conn)
    df_station.to_csv(reports_dir / "station_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'station_summary.csv'}")

    # 6. Station Seasonal Ranking Stability
    print("\n6. Analyzing Station Ranking Stability across seasons...")
    ranking_records = []
    seasons = ['Winter', 'Summer', 'Monsoon', 'Post-Monsoon']
    for season in seasons:
        sub = df_seasonal[df_seasonal['season'] == season].copy()
        sub['aqi_rank'] = sub['aqi_mean'].rank(ascending=False, method='min').astype(int)
        sub['pm25_rank'] = sub['pm25_mean'].rank(ascending=False, method='min').astype(int)
        sub['pm10_rank'] = sub['pm10_mean'].rank(ascending=False, method='min').astype(int)
        for _, row in sub.iterrows():
            ranking_records.append({
                "season": season,
                "station_name": row["station_name"],
                "aqi_mean": row["aqi_mean"],
                "aqi_rank": row["aqi_rank"],
                "pm25_mean": row["pm25_mean"],
                "pm25_rank": row["pm25_rank"],
                "pm10_mean": row["pm10_mean"],
                "pm10_rank": row["pm10_rank"],
            })
    df_rankings = pd.DataFrame(ranking_records)
    df_rankings.to_csv(reports_dir / "station_seasonal_ranking.csv", index=False)
    print(f"  Saved {reports_dir / 'station_seasonal_ranking.csv'}")

    conn.close()
    print("=== TEMPORAL, SEASONAL & STATION ANALYSIS COMPLETED ===")

if __name__ == "__main__":
    run_temporal_and_station_analysis()

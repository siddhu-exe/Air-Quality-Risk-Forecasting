"""
src/eda/advanced_statistical_analysis.py

Executes:
1. Spatial cross-station correlation (AQI, PM2.5, PM10)
2. Pollutant correlation matrix & multi-pollutant summaries
3. AQI distribution percentiles and extreme episode detection
4. Autocorrelation & persistence analysis (lag 1, 6, 12, 24, 48, 168)
5. Environmental variable usability & relationship with pollution

Outputs:
- reports/eda/spatial_correlation_matrix.csv
- reports/eda/correlation_matrix.csv
- reports/eda/pollutant_summary.csv
- reports/eda/episode_summary.csv
- reports/eda/autocorrelation_summary.csv
- reports/eda/environmental_summary.csv
"""

from __future__ import annotations
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import numpy as np
from scipy import stats

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_DIR / "etl"))

from load_postgres import load_env, get_connection

def run_advanced_statistical_analysis():
    env = load_env()
    conn = get_connection(env)
    reports_dir = PROJECT_DIR / "reports" / "eda"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=== STARTING ADVANCED STATISTICAL, SPATIAL & EPISODE ANALYSIS ===")

    # 1. Spatial Cross-Station Correlation
    print("\n1. Computing Spatial Cross-Station Correlations...")
    # Pivot CAAQMS PM2.5 across all stations on common timestamps
    piv_pm25_query = """
    SELECT
        c.timestamp,
        s.station_name,
        c.pm25
    FROM caaqms_hourly c
    JOIN stations s ON c.station_id = s.station_id
    WHERE c.timestamp >= '2024-01-01' AND c.timestamp <= '2025-12-31'
    ORDER BY c.timestamp;
    """
    df_pm25_raw = pd.read_sql_query(piv_pm25_query, conn)
    piv_pm25 = df_pm25_raw.pivot(index='timestamp', columns='station_name', values='pm25')
    spatial_pm25_corr = piv_pm25.corr(method='pearson').round(3)

    # Pivot AQI across all stations for 2025
    piv_aqi_query = """
    SELECT
        a.timestamp,
        s.station_name,
        a.aqi_value
    FROM aqi_hourly a
    JOIN stations s ON a.station_id = s.station_id
    ORDER BY a.timestamp;
    """
    df_aqi_raw = pd.read_sql_query(piv_aqi_query, conn)
    piv_aqi = df_aqi_raw.pivot(index='timestamp', columns='station_name', values='aqi_value')
    spatial_aqi_corr = piv_aqi.corr(method='pearson').round(3)

    # Save spatial correlation tables
    spatial_pm25_corr.to_csv(reports_dir / "spatial_pm25_correlation.csv")
    spatial_aqi_corr.to_csv(reports_dir / "spatial_aqi_correlation.csv")
    print(f"  Saved {reports_dir / 'spatial_pm25_correlation.csv'} and {reports_dir / 'spatial_aqi_correlation.csv'}")

    # 2. Comprehensive Pollutant Relationships & Correlation Matrix
    print("\n2. Computing Pollutant & Weather Correlation Matrix...")
    corr_vars_query = """
    SELECT
        c.station_id,
        c.timestamp,
        c.pm25,
        c.pm10,
        c.no,
        c.no2,
        c.nox,
        c.nh3,
        c.so2,
        c.co,
        c.o3,
        c.benzene,
        c.toluene,
        c.temperature,
        c.humidity,
        c.wind_speed,
        c.wind_direction,
        c.rainfall,
        c.solar_radiation,
        c.barometric_pressure,
        a.aqi_value
    FROM caaqms_hourly c
    LEFT JOIN aqi_hourly a ON c.station_id = a.station_id AND c.timestamp = a.timestamp;
    """
    df_corr_raw = pd.read_sql_query(corr_vars_query, conn)
    features_list = [
        'pm25', 'pm10', 'no', 'no2', 'nox', 'nh3', 'so2', 'co', 'o3',
        'benzene', 'toluene', 'temperature', 'humidity', 'wind_speed',
        'solar_radiation', 'barometric_pressure', 'aqi_value'
    ]
    df_feat = df_corr_raw[features_list]

    pearson_corr = df_feat.corr(method='pearson').round(3)
    spearman_corr = df_feat.corr(method='spearman').round(3)
    pearson_corr.to_csv(reports_dir / "correlation_matrix.csv")
    spearman_corr.to_csv(reports_dir / "spearman_correlation_matrix.csv")
    print(f"  Saved {reports_dir / 'correlation_matrix.csv'} (Pearson & Spearman)")

    # 3. Detailed Pollutant Statistical Summary Table
    print("\n3. Calculating Pollutant Statistical Distribution Summaries...")
    pol_stats_list = []
    for var in features_list:
        s = df_feat[var].dropna()
        if len(s) == 0:
            continue
        pol_stats_list.append({
            "variable": var,
            "count": len(s),
            "mean": round(s.mean(), 2),
            "std": round(s.std(), 2),
            "min": round(s.min(), 2),
            "p25": round(s.quantile(0.25), 2),
            "median": round(s.median(), 2),
            "p75": round(s.quantile(0.75), 2),
            "p90": round(s.quantile(0.90), 2),
            "p95": round(s.quantile(0.95), 2),
            "p99": round(s.quantile(0.99), 2),
            "max": round(s.max(), 2),
            "skewness": round(s.skew(), 2),
            "kurtosis": round(s.kurtosis(), 2),
            "pm25_pearson_corr": round(s.corr(df_feat['pm25']), 3),
            "aqi_pearson_corr": round(s.corr(df_feat['aqi_value']), 3) if var != 'aqi_value' else 1.0
        })
    df_pol_summary = pd.DataFrame(pol_stats_list)
    df_pol_summary.to_csv(reports_dir / "pollutant_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'pollutant_summary.csv'}")

    # 4. AQI Extreme Episodes Analysis
    # Definition: Continuous sequences of hourly AQI >= 400 (Severe/Severe+) lasting >= 6 hours
    print("\n4. Identifying High-Pollution Extreme Episodes (AQI >= 400, duration >= 6h)...")
    episode_records = []
    for st_name in piv_aqi.columns:
        s_series = piv_aqi[st_name].dropna().sort_index()
        is_severe = (s_series >= 400)

        # Find contiguous blocks
        blocks = (is_severe != is_severe.shift()).cumsum()
        for block_id, group in s_series.groupby(blocks):
            if group.iloc[0] >= 400 and len(group) >= 6:
                start_ts = group.index[0]
                end_ts = group.index[-1]
                duration_hrs = len(group)
                max_aqi = group.max()
                mean_aqi = round(group.mean(), 1)
                episode_records.append({
                    "station_name": st_name,
                    "start_time": str(start_ts),
                    "end_time": str(end_ts),
                    "duration_hours": duration_hrs,
                    "max_aqi": max_aqi,
                    "mean_aqi": mean_aqi,
                    "start_month": start_ts.month,
                    "start_year": start_ts.year
                })

    df_episodes = pd.DataFrame(episode_records)
    if not df_episodes.empty:
        df_episodes = df_episodes.sort_values(by="duration_hours", ascending=False)
    df_episodes.to_csv(reports_dir / "episode_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'episode_summary.csv'} ({len(df_episodes)} severe episodes identified)")

    # 5. Autocorrelation & Persistence Analysis
    print("\n5. Computing Temporal Autocorrelation & Persistence (Lags 1, 6, 12, 24, 48, 168)...")
    lags = [1, 6, 12, 24, 48, 168]
    autocorr_rows = []

    for st_name in piv_aqi.columns:
        s_aqi = piv_aqi[st_name].dropna()
        s_pm25 = piv_pm25[st_name].dropna()

        row = {"station_name": st_name}
        for lag in lags:
            ac_aqi = s_aqi.autocorr(lag=lag) if len(s_aqi) > lag else np.nan
            ac_pm25 = s_pm25.autocorr(lag=lag) if len(s_pm25) > lag else np.nan
            row[f"aqi_lag_{lag}"] = round(ac_aqi, 3)
            row[f"pm25_lag_{lag}"] = round(ac_pm25, 3)
        autocorr_rows.append(row)

    df_autocorr = pd.DataFrame(autocorr_rows)
    df_autocorr.to_csv(reports_dir / "autocorrelation_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'autocorrelation_summary.csv'}")

    # 6. Environmental & Meteorological Usability Summary
    print("\n6. Assessing Meteorological Variable Usability...")
    env_vars = ['temperature', 'humidity', 'wind_speed', 'wind_direction', 'rainfall', 'solar_radiation', 'barometric_pressure']
    env_summary_list = []
    for ev in env_vars:
        sub = df_corr_raw[[ev, 'pm25', 'aqi_value', 'station_id']].dropna(subset=[ev])
        tot_avail = len(sub)
        p_corr_pm25 = sub[ev].corr(sub['pm25'])
        s_corr_pm25 = sub[ev].corr(sub['pm25'], method='spearman')
        p_corr_aqi = sub[ev].corr(sub['aqi_value'])
        s_corr_aqi = sub[ev].corr(sub['aqi_value'], method='spearman')

        env_summary_list.append({
            "environmental_variable": ev,
            "available_records": tot_avail,
            "overall_pct_available": round((tot_avail / len(df_corr_raw)) * 100.0, 1),
            "pm25_pearson_corr": round(p_corr_pm25, 3),
            "pm25_spearman_corr": round(s_corr_pm25, 3),
            "aqi_pearson_corr": round(p_corr_aqi, 3),
            "aqi_spearman_corr": round(s_corr_aqi, 3),
            "usability_assessment": "High" if tot_avail > 130000 and ev != 'rainfall' else ("Moderate" if ev == 'barometric_pressure' else "Low/Sparse")
        })
    df_env = pd.DataFrame(env_summary_list)
    df_env.to_csv(reports_dir / "environmental_summary.csv", index=False)
    print(f"  Saved {reports_dir / 'environmental_summary.csv'}")

    conn.close()
    print("=== ADVANCED STATISTICAL, SPATIAL & EPISODE ANALYSIS COMPLETED ===")

if __name__ == "__main__":
    run_advanced_statistical_analysis()

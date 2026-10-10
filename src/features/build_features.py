"""
build_features.py
Constructs a leakage-safe tabular feature matrix for Air Quality Risk Forecasting
from PostgreSQL air_quality_db across 7 Delhi CAAQMS stations.
"""

import os
import sys
import numpy as np
import pandas as pd
import psycopg2
from pathlib import Path

# Allow `python src/features/build_features.py` (script dir, not repo root, is on sys.path).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.features.compute_cpcb_aqi import (
    DEFAULT_RAW_DIR,
    POLLUTANT_COLUMNS,
    STATION_IDS,
    _station_for_folder,
    load_official_aqi,
)

# Database credentials
DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": os.getenv("POSTGRES_PORT", "5433"),
    "dbname": os.getenv("POSTGRES_DB", "air_quality_db"),
    "user": os.getenv("POSTGRES_USER", "aq_admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "aq_password_2025"),
}

PROCESSED_DATA_DIR = Path("data/processed")
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = Path("reports/features")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Top correlated neighbor mapping based on Phase 4 empirical correlation matrix
TOP_NEIGHBORS = {
    'Anand Vihar': 'Dwarka-Sector 8',
    'Bawana': 'R K Puram',
    'Dwarka-Sector 8': 'R K Puram',
    'ITO': 'R K Puram',
    'Jahangirpuri': 'Bawana',
    'Punjabi Bagh': 'R K Puram',
    'R K Puram': 'Punjabi Bagh',
}

# The CAAQMS columns the feature engineering expects, mapped from the raw CSV headers.
RAW_CSV_TO_CAAQMS = {
    **POLLUTANT_COLUMNS,
    "NO (µg/m³)": "no",
    "NOx (ppb)": "nox",
    "AT (°C)": "temperature",
    "RH (%)": "humidity",
    "WS (m/s)": "wind_speed",
    "SR (W/mt2)": "solar_radiation",
}

OFFLINE_START = pd.Timestamp("2024-01-01 00:00:00", tz='Asia/Kolkata')
OFFLINE_END = pd.Timestamp("2025-12-31 23:00:00", tz='Asia/Kolkata')


def _stations_frame():
    """Minimal stations table (id, name); coordinates are not needed for features."""
    return pd.DataFrame(
        [{"station_id": sid, "station_name": name, "city": "Delhi"}
         for name, sid in sorted(STATION_IDS.items(), key=lambda kv: kv[1])]
    )


def load_raw_data_from_db():
    """Extracts CAAQMS and AQI hourly tables from PostgreSQL."""
    conn = psycopg2.connect(**DB_PARAMS)

    # Load stations
    stations_df = pd.read_sql_query(
        "SELECT station_id, station_name, city, operator, latitude, longitude FROM stations ORDER BY station_id;",
        conn
    )

    # Load CAAQMS hourly (2024 to 2025)
    caaqms_query = """
    SELECT
        station_id,
        timestamp,
        pm25,
        pm10,
        no,
        no2,
        nox,
        nh3,
        so2,
        co,
        o3,
        temperature,
        humidity,
        wind_speed,
        solar_radiation
    FROM caaqms_hourly
    WHERE timestamp >= '2023-12-31 18:30:00+00' AND timestamp <= '2025-12-31 18:30:00+00'
    ORDER BY station_id, timestamp;
    """
    caaqms_df = pd.read_sql_query(caaqms_query, conn)

    # Load AQI hourly (2025)
    aqi_query = """
    SELECT
        station_id,
        timestamp,
        aqi_value
    FROM aqi_hourly
    WHERE timestamp >= '2024-12-31 18:30:00+00' AND timestamp <= '2025-12-31 18:30:00+00'
    ORDER BY station_id, timestamp;
    """
    aqi_df = pd.read_sql_query(aqi_query, conn)
    conn.close()

    # Convert timestamps to Asia/Kolkata
    caaqms_df['timestamp'] = pd.to_datetime(caaqms_df['timestamp']).dt.tz_convert('Asia/Kolkata')
    aqi_df['timestamp'] = pd.to_datetime(aqi_df['timestamp']).dt.tz_convert('Asia/Kolkata')

    print(f"Loaded {len(caaqms_df):,} CAAQMS records and {len(aqi_df):,} AQI records from PostgreSQL.")
    return stations_df, caaqms_df, aqi_df


def load_raw_data_offline(start=None, end=None):
    """Extracts CAAQMS + AQI from the raw CSVs and the recomputed AQI parquet.

    Used when PostgreSQL is unavailable. The target AQI is the official series
    for 2025 and the CPCB-recomputed series (``aqi_source='recomputed'``) for
    2023-2024, so the training window can include a prior winter.
    """
    start = start if start is not None else OFFLINE_START
    end = end if end is not None else OFFLINE_END
    years = list(range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1))

    caaqms_frames = []
    folders = sorted(os.listdir(DEFAULT_RAW_DIR))
    for folder in folders:
        station = _station_for_folder(folder)
        raw_dir = Path(DEFAULT_RAW_DIR) / folder / "Raw Data"
        if station is None or not raw_dir.is_dir():
            continue
        for year in years:
            for csv_path in raw_dir.glob(f"{year}_*_1H.csv"):
                frame = pd.read_csv(csv_path).rename(columns=RAW_CSV_TO_CAAQMS)
                keep = ["Timestamp"] + [c for c in RAW_CSV_TO_CAAQMS.values() if c in frame.columns]
                caaqms_frames.append(
                    frame[keep].assign(station_id=STATION_IDS[station], station_name=station)
                )
    caaqms_df = pd.concat(caaqms_frames, ignore_index=True).rename(columns={"Timestamp": "timestamp"})
    caaqms_df["timestamp"] = pd.to_datetime(caaqms_df["timestamp"])
    caaqms_df = caaqms_df.loc[
        (caaqms_df["timestamp"] >= pd.Timestamp(start).tz_localize(None))
        & (caaqms_df["timestamp"] <= pd.Timestamp(end).tz_localize(None))
    ]

    aqi_parts = []
    official = load_official_aqi([2025])
    official = official.rename(columns={"aqi_official": "aqi_value"})
    official["aqi_source"] = "official"
    official = official.merge(_stations_frame()[["station_id", "station_name"]], on="station_name")
    aqi_parts.append(official[["station_id", "station_name", "timestamp", "aqi_value", "aqi_source"]])

    recomputed_path = PROCESSED_DATA_DIR / "recomputed_aqi.parquet"
    if recomputed_path.exists():
        recomputed = pd.read_parquet(recomputed_path)
        recomputed["aqi_source"] = "recomputed"
        aqi_parts.append(
            recomputed[["station_id", "station_name", "timestamp", "aqi_value", "aqi_source"]]
        )
    aqi_df = pd.concat(aqi_parts, ignore_index=True)

    # Official AQI wins wherever both exist; recomputed only backfills pre-2025.
    aqi_df["_priority"] = (aqi_df["aqi_source"] == "official").astype(int)
    aqi_df = (
        aqi_df.sort_values("_priority")
        .drop_duplicates(["station_id", "timestamp"], keep="last")
        .drop(columns="_priority")
    )

    for column in ("timestamp",):
        caaqms_df[column] = pd.to_datetime(caaqms_df[column]).dt.tz_localize("Asia/Kolkata")
        aqi_df[column] = pd.to_datetime(aqi_df[column]).dt.tz_localize("Asia/Kolkata")

    print(
        f"Loaded {len(caaqms_df):,} CAAQMS records and {len(aqi_df):,} AQI records offline."
    )
    return _stations_frame(), caaqms_df, aqi_df


def engineer_station_features(station_id, station_name, caaqms_sub, aqi_sub, full_idx=None):
    """
    Constructs causal temporal, lag, rolling, and meteorological features for a single station.
    Strictly uses historical values (<= t) for feature calculation.
    """
    if full_idx is None:
        full_idx = pd.date_range("2024-01-01 00:00:00", "2025-12-31 23:00:00", freq='h', tz='Asia/Kolkata')

    c_indexed = caaqms_sub.sort_values('timestamp').drop_duplicates(subset=['timestamp']).set_index('timestamp').reindex(full_idx)
    a_indexed = aqi_sub.sort_values('timestamp').drop_duplicates(subset=['timestamp']).set_index('timestamp').reindex(full_idx)

    feat_dict = {
        'station_id': station_id,
        'station_name': station_name,
        'timestamp': full_idx,
    }

    # Base series
    aqi_s = a_indexed['aqi_value']
    pm25_s = c_indexed['pm25']
    feat_dict['aqi_source'] = (
        a_indexed['aqi_source'].ffill().bfill().values
        if 'aqi_source' in a_indexed.columns
        else 'official'
    )

    # -------------------------------------------------------------
    # Group A: Recent AQI Lags & Current Value (10 features)
    # -------------------------------------------------------------
    feat_dict['aqi_curr'] = aqi_s.values
    for lag in [1, 2, 3, 6, 12, 24, 48, 72, 168]:
        feat_dict[f'aqi_lag_{lag}h'] = aqi_s.shift(lag).values

    # -------------------------------------------------------------
    # Group B: Pollutant Lags (35 features)
    # -------------------------------------------------------------
    pollutants = ['pm25', 'pm10', 'no2', 'nox', 'so2', 'co', 'o3']
    for p in pollutants:
        p_s = c_indexed[p] if p in c_indexed.columns else pd.Series(np.nan, index=full_idx)
        feat_dict[f'{p}_curr'] = p_s.values
        for lag in [1, 6, 12, 24]:
            feat_dict[f'{p}_lag_{lag}h'] = p_s.shift(lag).values

    # -------------------------------------------------------------
    # Group C: Causal Backward Rolling Statistics (32 features)
    # Windows: 3h, 6h, 12h, 24h over [t-W+1, t]
    # -------------------------------------------------------------
    for w in [3, 6, 12, 24]:
        min_p = max(1, w // 2)
        # AQI rolling
        feat_dict[f'aqi_roll_mean_{w}h'] = aqi_s.rolling(window=w, min_periods=min_p).mean().values
        feat_dict[f'aqi_roll_std_{w}h'] = aqi_s.rolling(window=w, min_periods=min_p).std().values
        feat_dict[f'aqi_roll_min_{w}h'] = aqi_s.rolling(window=w, min_periods=min_p).min().values
        feat_dict[f'aqi_roll_max_{w}h'] = aqi_s.rolling(window=w, min_periods=min_p).max().values
        # PM2.5 rolling
        feat_dict[f'pm25_roll_mean_{w}h'] = pm25_s.rolling(window=w, min_periods=min_p).mean().values
        feat_dict[f'pm25_roll_std_{w}h'] = pm25_s.rolling(window=w, min_periods=min_p).std().values
        feat_dict[f'pm25_roll_min_{w}h'] = pm25_s.rolling(window=w, min_periods=min_p).min().values
        feat_dict[f'pm25_roll_max_{w}h'] = pm25_s.rolling(window=w, min_periods=min_p).max().values

    # -------------------------------------------------------------
    # Group D: Temporal & Cyclical Features (13 features)
    # -------------------------------------------------------------
    hour = full_idx.hour
    dow = full_idx.dayofweek
    month = full_idx.month
    doy = full_idx.dayofyear

    feat_dict['hour'] = hour
    feat_dict['day_of_week'] = dow
    feat_dict['month'] = month
    feat_dict['day_of_year'] = doy
    feat_dict['is_weekend'] = (dow >= 5).astype(int)

    feat_dict['sin_hour'] = np.sin(2 * np.pi * hour / 24.0)
    feat_dict['cos_hour'] = np.cos(2 * np.pi * hour / 24.0)
    feat_dict['sin_dow'] = np.sin(2 * np.pi * dow / 7.0)
    feat_dict['cos_dow'] = np.cos(2 * np.pi * dow / 7.0)
    feat_dict['sin_month'] = np.sin(2 * np.pi * (month - 1) / 12.0)
    feat_dict['cos_month'] = np.cos(2 * np.pi * (month - 1) / 12.0)
    feat_dict['sin_doy'] = np.sin(2 * np.pi * (doy - 1) / 365.25)
    feat_dict['cos_doy'] = np.cos(2 * np.pi * (doy - 1) / 365.25)

    # -------------------------------------------------------------
    # Group E: Seasonality Indicators (IMD) (4 features)
    # -------------------------------------------------------------
    feat_dict['is_winter'] = month.isin([12, 1, 2]).astype(int)
    feat_dict['is_summer'] = month.isin([3, 4, 5]).astype(int)
    feat_dict['is_monsoon'] = month.isin([6, 7, 8, 9]).astype(int)
    feat_dict['is_post_monsoon'] = month.isin([10, 11]).astype(int)

    # -------------------------------------------------------------
    # Group F: Meteorological Features (24 features)
    # -------------------------------------------------------------
    meteo_vars = {
        'temp': 'temperature',
        'humidity': 'humidity',
        'wind_speed': 'wind_speed',
        'solar_rad': 'solar_radiation'
    }
    for m_short, m_col in meteo_vars.items():
        m_s = c_indexed[m_col] if m_col in c_indexed.columns else pd.Series(np.nan, index=full_idx)
        feat_dict[f'{m_short}_curr'] = m_s.values
        for lag in [1, 6, 24]:
            feat_dict[f'{m_short}_lag_{lag}h'] = m_s.shift(lag).values
        for w in [6, 24]:
            feat_dict[f'{m_short}_roll_mean_{w}h'] = m_s.rolling(window=w, min_periods=1).mean().values

    # -------------------------------------------------------------
    # Targets: Forward Lead Horizons (t+1, t+6, t+24)
    # -------------------------------------------------------------
    feat_dict['target_aqi_1h'] = aqi_s.shift(-1).values
    feat_dict['target_aqi_6h'] = aqi_s.shift(-6).values
    feat_dict['target_aqi_24h'] = aqi_s.shift(-24).values
    # Raw PM2.5 targets: unlike the smoothed AQI these have real hourly dynamics,
    # so model skill vs persistence is actually measurable (improvement plan T2.3).
    feat_dict['target_pm25_1h'] = pm25_s.shift(-1).values
    feat_dict['target_pm25_6h'] = pm25_s.shift(-6).values
    feat_dict['target_pm25_24h'] = pm25_s.shift(-24).values

    return pd.DataFrame(feat_dict)


def assemble_feature_matrix(stations_df, caaqms_df, aqi_df, full_start, full_end,
                            window_start, window_end, output_path, write_manifest=True):
    """Builds the per-station + cross-station feature matrix for a date window."""
    full_idx = pd.date_range(
        pd.Timestamp(full_start).tz_convert("Asia/Kolkata").floor("h"),
        pd.Timestamp(full_end).tz_convert("Asia/Kolkata").floor("h"),
        freq='h', tz='Asia/Kolkata',
    )
    station_matrices = []
    print("\n--- Engineering Features per Station ---")
    for _, srow in stations_df.iterrows():
        sid = srow['station_id']
        sname = srow['station_name']
        print(f"Processing station: {sname} (ID: {sid})...")

        c_sub = caaqms_df[caaqms_df['station_id'] == sid].copy()
        a_sub = aqi_df[aqi_df['station_id'] == sid].copy()

        feat_df = engineer_station_features(sid, sname, c_sub, a_sub, full_idx=full_idx)
        station_matrices.append(feat_df)

    full_df = pd.concat(station_matrices, ignore_index=True)

    # -------------------------------------------------------------
    # Group G: Cross-Station Spatial Network Signals (6 features)
    # Computed using strictly lagged lag-1h values (<= t-1) to avoid leakage
    # -------------------------------------------------------------
    print("\n--- Computing Cross-Station Spatial Signals (Group G) ---")

    # 1. Network-wide mean/min/max excluding self at timestamp t
    spatial_agg = full_df.groupby('timestamp').agg(
        net_total_aqi_lag_1h=('aqi_lag_1h', 'sum'),
        net_count_aqi_lag_1h=('aqi_lag_1h', 'count'),
        net_total_pm25_lag_1h=('pm25_lag_1h', 'sum'),
        net_count_pm25_lag_1h=('pm25_lag_1h', 'count'),
        network_max_aqi_lag_1h=('aqi_lag_1h', 'max'),
        network_min_aqi_lag_1h=('aqi_lag_1h', 'min'),
    ).reset_index()

    full_df = full_df.merge(spatial_agg, on='timestamp', how='left')

    # Network mean excluding self: (Total - Self) / (Count - 1)
    self_aqi_lag1 = full_df['aqi_lag_1h'].fillna(0)
    self_aqi_valid = full_df['aqi_lag_1h'].notna().astype(int)
    denom_aqi = (full_df['net_count_aqi_lag_1h'] - self_aqi_valid).clip(lower=1)
    full_df['network_mean_aqi_lag_1h'] = (full_df['net_total_aqi_lag_1h'].fillna(0) - self_aqi_lag1) / denom_aqi

    self_pm25_lag1 = full_df['pm25_lag_1h'].fillna(0)
    self_pm25_valid = full_df['pm25_lag_1h'].notna().astype(int)
    denom_pm25 = (full_df['net_count_pm25_lag_1h'] - self_pm25_valid).clip(lower=1)
    full_df['network_mean_pm25_lag_1h'] = (full_df['net_total_pm25_lag_1h'].fillna(0) - self_pm25_lag1) / denom_pm25

    # 2. Vectorized Top-correlated neighbor station lag-1 features
    neighbor_lookup = full_df[['timestamp', 'station_name', 'aqi_lag_1h', 'pm25_lag_1h']].rename(
        columns={
            'station_name': 'neighbor_station_name',
            'aqi_lag_1h': 'top_neighbor_aqi_lag_1h',
            'pm25_lag_1h': 'top_neighbor_pm25_lag_1h'
        }
    )

    full_df['neighbor_station_name'] = full_df['station_name'].map(TOP_NEIGHBORS)
    full_df = full_df.merge(neighbor_lookup, on=['timestamp', 'neighbor_station_name'], how='left')

    # Drop temporary spatial aggregation columns
    full_df.drop(columns=[
        'neighbor_station_name',
        'net_total_aqi_lag_1h', 'net_count_aqi_lag_1h',
        'net_total_pm25_lag_1h', 'net_count_pm25_lag_1h'
    ], inplace=True)

    # -------------------------------------------------------------
    # Filter to the requested window where a current AQI exists
    # -------------------------------------------------------------
    print(f"\n--- Filtering to {window_start.date()} .. {window_end.date()} ---")
    in_window = (full_df['timestamp'] >= pd.Timestamp(window_start)) & \
                (full_df['timestamp'] <= pd.Timestamp(window_end))
    has_current_aqi = full_df['aqi_curr'].notna()

    dataset = full_df[in_window & has_current_aqi].copy().sort_values(['station_id', 'timestamp']).reset_index(drop=True)

    # Save output parquet
    dataset.to_parquet(output_path, index=False)
    print(f"Saved feature matrix to: {output_path} (Shape: {dataset.shape})")

    # Summary of columns by group
    feature_cols = [c for c in dataset.columns if c not in [
        'station_id', 'station_name', 'timestamp',
        'target_aqi_1h', 'target_aqi_6h', 'target_aqi_24h',
        'target_pm25_1h', 'target_pm25_6h', 'target_pm25_24h',
    ]]
    print(f"Total Engineered Feature Columns: {len(feature_cols)}")

    # Group assignments for manifest
    def get_feature_group(col):
        if col.startswith('aqi_lag_') or col == 'aqi_curr':
            return 'Group A: Recent AQI Lags'
        elif '_roll_' in col and ('aqi_' in col or 'pm25_' in col):
            return 'Group C: Causal Rolling Statistics'
        elif any(col.startswith(f'{p}_') for p in ['pm25', 'pm10', 'no2', 'nox', 'so2', 'co', 'o3']):
            return 'Group B: Pollutant Lags'
        elif col in ['hour', 'day_of_week', 'month', 'day_of_year', 'is_weekend',
                     'sin_hour', 'cos_hour', 'sin_dow', 'cos_dow', 'sin_month', 'cos_month', 'sin_doy', 'cos_doy']:
            return 'Group D: Temporal & Cyclical'
        elif col.startswith('is_') and col != 'is_weekend':
            return 'Group E: Seasonality Indicators'
        elif any(k in col for k in ['temp_', 'humidity_', 'wind_speed_', 'solar_rad_']):
            return 'Group F: Meteorology'
        elif 'network_' in col or 'top_neighbor_' in col:
            return 'Group G: Cross-Station Spatial'
        else:
            return 'Other / Metadata'

    manifest_df = pd.DataFrame({
        "feature_name": feature_cols,
        "group": [get_feature_group(c) for c in feature_cols],
        "dtype": [str(dataset[c].dtype) for c in feature_cols],
        "non_null_count": [int(dataset[c].notna().sum()) for c in feature_cols],
        "missing_pct": [round(dataset[c].isna().mean() * 100, 2) for c in feature_cols]
    })
    if write_manifest:
        manifest_df.to_csv(REPORTS_DIR / "feature_manifest.csv", index=False)
        print(f"Feature manifest saved to: {REPORTS_DIR / 'feature_manifest.csv'}")

    print("\n--- Feature Count by Group ---")
    print(manifest_df['group'].value_counts())

    return dataset


def build_feature_matrix(source="db", start=None, end=None, output_path=None):
    """Orchestrates multi-station feature engineering and cross-station signals.

    ``source='db'`` keeps the original PostgreSQL behaviour (2025 output frame);
    ``source='offline'`` reads the raw CSVs plus the recomputed AQI parquet so
    the extended 2024-2025 training window can be built without Postgres.
    """
    start = start if start is not None else OFFLINE_START
    end = end if end is not None else OFFLINE_END
    output_path = Path(output_path) if output_path is not None else PROCESSED_DATA_DIR / "features_2025.parquet"

    if source == "offline":
        stations_df, caaqms_df, aqi_df = load_raw_data_offline(start, end)
        window_start, window_end = start, end
    else:
        stations_df, caaqms_df, aqi_df = load_raw_data_from_db()
        window_start = pd.Timestamp("2025-01-01 00:00:00", tz='Asia/Kolkata')
        window_end = pd.Timestamp("2025-12-31 23:00:00", tz='Asia/Kolkata')

    return assemble_feature_matrix(
        stations_df, caaqms_df, aqi_df,
        full_start=start, full_end=end,
        window_start=window_start, window_end=window_end,
        output_path=output_path,
    )


if __name__ == "__main__":
    build_feature_matrix()

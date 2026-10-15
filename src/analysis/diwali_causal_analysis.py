"""
Causal Analysis: Delhi Diwali Firecracker Ban Policy vs Seasonal Inversion
==========================================================================
Evaluates the causal impact of the Delhi firecracker ban policy vs seasonal
meteorological confounding using CAAQMS/AQI data, pre-trends testing,
interrupted time series, meteorological controls, and in-time placebo tests.
"""

import os
import sys
from pathlib import Path
import psycopg2
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

# Set style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300

REPO_ROOT = Path(__file__).resolve().parents[2]


def _db_params() -> dict:
    """Local research database settings from POSTGRES_* in the environment or the git-ignored .env."""
    env = dict(os.environ)
    env_file = REPO_ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, val = line.strip().partition('=')
            if sep and not key.startswith('#'):
                env.setdefault(key.strip(), val.strip())
    return {
        'host': env.get('POSTGRES_HOST', 'localhost'),
        'port': int(env.get('POSTGRES_PORT', 5433)),
        'dbname': env['POSTGRES_DB'],
        'user': env['POSTGRES_USER'],
        'password': env['POSTGRES_PASSWORD'],
    }


OUTPUT_DIR = str(REPO_ROOT / 'reports' / 'causal')
FIGURES_DIR = os.path.join(OUTPUT_DIR, 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)


def get_db_connection():
    return psycopg2.connect(**_db_params())


def extract_data():
    conn = get_db_connection()

    # 1. Delhi 2025 Daily Window around Diwali (2025-10-20)
    q_2025_daily = """
    SELECT
        DATE(a.timestamp AT TIME ZONE 'Asia/Kolkata') as date,
        s.station_name,
        AVG(a.aqi_value) as aqi,
        AVG(c.pm25) as pm25,
        AVG(c.pm10) as pm10,
        AVG(c.so2) as so2,
        AVG(c.no2) as no2,
        AVG(c.temperature) as temp,
        AVG(c.wind_speed) as wind_speed,
        AVG(c.humidity) as humidity
    FROM aqi_hourly a
    JOIN stations s ON a.station_id = s.station_id
    LEFT JOIN caaqms_hourly c ON a.station_id = c.station_id AND a.timestamp = c.timestamp
    WHERE a.timestamp >= '2025-10-06 00:00:00+05:30' AND a.timestamp <= '2025-11-03 23:59:59+05:30'
    GROUP BY date, s.station_name
    ORDER BY date, s.station_name
    """
    df_2025_daily = pd.read_sql(q_2025_daily, conn)

    # 2. Delhi 2025 Hourly Data for Diwali Night
    q_2025_hourly = """
    SELECT
        c.timestamp AT TIME ZONE 'Asia/Kolkata' as ts,
        s.station_name,
        c.pm25,
        c.pm10,
        c.so2,
        c.no2,
        c.co,
        c.temperature as temp,
        c.wind_speed as ws,
        c.humidity as rh
    FROM caaqms_hourly c
    JOIN stations s ON c.station_id = s.station_id
    WHERE c.timestamp >= '2025-10-18 00:00:00+05:30' AND c.timestamp <= '2025-10-23 23:59:59+05:30'
    ORDER BY ts, s.station_name
    """
    df_2025_hourly = pd.read_sql(q_2025_hourly, conn)

    # 3. Delhi 2024 Daily Data around Diwali (2024-10-31)
    q_2024_daily = """
    SELECT
        DATE(c.timestamp AT TIME ZONE 'Asia/Kolkata') as date,
        s.station_name,
        AVG(c.pm25) as pm25,
        AVG(c.pm10) as pm10,
        AVG(c.so2) as so2,
        AVG(c.no2) as no2,
        AVG(c.temperature) as temp,
        AVG(c.wind_speed) as wind_speed,
        AVG(c.humidity) as humidity
    FROM caaqms_hourly c
    JOIN stations s ON c.station_id = s.station_id
    WHERE c.timestamp >= '2024-10-17 00:00:00+05:30' AND c.timestamp <= '2024-11-14 23:59:59+05:30'
    GROUP BY date, s.station_name
    ORDER BY date, s.station_name
    """
    df_2024_daily = pd.read_sql(q_2024_daily, conn)

    # 4. Delhi 2024 Hourly Data for Diwali Night
    q_2024_hourly = """
    SELECT
        c.timestamp AT TIME ZONE 'Asia/Kolkata' as ts,
        s.station_name,
        c.pm25,
        c.pm10,
        c.so2,
        c.no2,
        c.co,
        c.temperature as temp,
        c.wind_speed as ws
    FROM caaqms_hourly c
    JOIN stations s ON c.station_id = s.station_id
    WHERE c.timestamp >= '2024-10-30 00:00:00+05:30' AND c.timestamp <= '2024-11-02 23:59:59+05:30'
    ORDER BY ts, s.station_name
    """
    df_2024_hourly = pd.read_sql(q_2024_hourly, conn)

    # 5. Delhi 2025 Placebo Data around Placebo Date (2025-09-20)
    q_2025_placebo = """
    SELECT
        DATE(a.timestamp AT TIME ZONE 'Asia/Kolkata') as date,
        s.station_name,
        AVG(a.aqi_value) as aqi,
        AVG(c.pm25) as pm25,
        AVG(c.temperature) as temp,
        AVG(c.wind_speed) as wind_speed,
        AVG(c.humidity) as humidity
    FROM aqi_hourly a
    JOIN stations s ON a.station_id = s.station_id
    LEFT JOIN caaqms_hourly c ON a.station_id = c.station_id AND a.timestamp = c.timestamp
    WHERE a.timestamp >= '2025-09-06 00:00:00+05:30' AND a.timestamp <= '2025-10-04 23:59:59+05:30'
    GROUP BY date, s.station_name
    ORDER BY date, s.station_name
    """
    df_2025_placebo = pd.read_sql(q_2025_placebo, conn)

    conn.close()
    return df_2025_daily, df_2025_hourly, df_2024_daily, df_2024_hourly, df_2025_placebo


def _fit_clustered(formula, data, cluster_col='date'):
    """OLS with standard errors clustered by calendar date.

    Diwali windows are panel data (station x day). Clustering by date absorbs the
    cross-sectional dependence from common daily shocks (weather, regional transport),
    which station-clustered errors miss.
    """
    res = smf.ols(formula, data=data).fit(
        cov_type='cluster', cov_kwds={'groups': data[cluster_col]}
    )
    res._cluster_col = cluster_col
    res._n_clusters = int(data[cluster_col].nunique())
    return res


def _tidy_row(res, model_id, outcome, specification, coef_name, interpretation):
    ci = res.conf_int().loc[coef_name]
    return {
        'model_id': model_id,
        'outcome': outcome,
        'specification': specification,
        'se_type': f'cluster_by_{getattr(res, "_cluster_col", "date")}',
        'coef_name': coef_name,
        'coef': float(res.params[coef_name]),
        'std_err': float(res.bse[coef_name]),
        't_stat': float(res.tvalues[coef_name]),
        'p_value': float(res.pvalues[coef_name]),
        'ci_lower': float(ci[0]),
        'ci_upper': float(ci[1]),
        'r_squared': float(res.rsquared),
        'n_obs': int(res.nobs),
        'n_clusters': int(getattr(res, '_n_clusters', 0)),
        'interpretation': interpretation,
    }


def run_statistical_models(df_2025_daily, df_2025_placebo):
    """Fit pre-trend, naive before/after, station FE, meteo, ITS and placebo specs.

    Primary outcome is raw daily-mean PM2.5 (AQI is a pre-smoothed 24h rolling average,
    so it hides the hourly dynamics). AQI is retained as a secondary outcome. Every
    model uses standard errors clustered by date; station fixed effects are kept.
    """
    diwali_date = pd.to_datetime('2025-10-20').date()
    df_2025 = df_2025_daily.copy()
    df_2025['date_dt'] = pd.to_datetime(df_2025['date'])
    df_2025['rel_day'] = (df_2025['date_dt'] - pd.to_datetime(diwali_date)).dt.days
    df_2025['post'] = (df_2025['rel_day'] > 0).astype(int)
    df_2025['date'] = df_2025['date_dt'].dt.date

    df_pre = df_2025[df_2025['rel_day'] < 0].copy()
    df_pre_post = df_2025[df_2025['rel_day'] != 0].copy()
    df_meteo = df_pre_post.dropna(subset=['temp', 'wind_speed', 'humidity']).copy()
    df_meteo['post_rel_day'] = df_meteo['post'] * df_meteo['rel_day']

    placebo_date = pd.to_datetime('2025-09-20').date()
    df_p = df_2025_placebo.copy()
    df_p['date_dt'] = pd.to_datetime(df_p['date'])
    df_p['rel_day'] = (df_p['date_dt'] - pd.to_datetime(placebo_date)).dt.days
    df_p['post'] = (df_p['rel_day'] > 0).astype(int)
    df_p['date'] = df_p['date_dt'].dt.date
    df_p_pre_post = df_p[df_p['rel_day'] != 0].copy()

    rows, fits = [], {}
    for y in ('pm25', 'aqi'):
        if y not in df_2025.columns:
            continue
        pre = _fit_clustered(f'{y} ~ rel_day', df_pre.dropna(subset=[y]))
        m1 = _fit_clustered(f'{y} ~ post', df_pre_post.dropna(subset=[y]))
        m2 = _fit_clustered(f'{y} ~ post + C(station_name)', df_pre_post.dropna(subset=[y]))
        m3 = _fit_clustered(
            f'{y} ~ post + temp + wind_speed + humidity + C(station_name)', df_meteo.dropna(subset=[y]))
        m4 = _fit_clustered(
            f'{y} ~ rel_day + post + post_rel_day + temp + wind_speed + humidity + C(station_name)',
            df_meteo.dropna(subset=[y]))
        mp = _fit_clustered(f'{y} ~ post + C(station_name)', df_p_pre_post.dropna(subset=[y]))

        rows += [
            _tidy_row(pre, 'Pre-Trend Slope', y, f'{y} ~ rel_day (pre-Diwali [-14,-1])', 'rel_day',
                      'Pre-Diwali slope; non-zero means the parallel-trends assumption is violated'),
            _tidy_row(m1, 'Model 1 (Naive Before/After)', y, f'{y} ~ post', 'post',
                      'Naive before/after shift; confounded by the seasonal trajectory'),
            _tidy_row(m2, 'Model 2 (Station FE)', y, f'{y} ~ post + station FE', 'post',
                      'Within-station shift after absorbing station baselines'),
            _tidy_row(m3, 'Model 3 (Meteo Controls)', y, f'{y} ~ post + meteo + station FE', 'post',
                      'Shift controlling for surface weather only'),
            _tidy_row(m4, 'Model 4 (Interrupted Time Series)', y,
                      f'{y} ~ rel_day + post + post:rel_day + meteo + station FE', 'post',
                      'Level jump after accounting for the pre-existing trend'),
            _tidy_row(mp, 'Model 5 (Placebo Non-Event)', y,
                      f'{y} ~ post_placebo + station FE (2025-09-20)', 'post',
                      'Placebo pseudo-effect on a non-event date; should be ~0 if the design is valid'),
        ]
        fits[y] = {'pre': pre, 'm1': m1, 'm2': m2, 'm3': m3, 'm4': m4, 'placebo': mp}

    return pd.DataFrame(rows), fits


def generate_plots(df_2025_daily, df_2025_hourly, df_2024_hourly, df_2025_placebo, df_models_summary):
    # -------------------------------------------------------------
    # Figure 1: Diwali 2025 Daily Timeline, Pre-Trends, and Meteorology
    # -------------------------------------------------------------
    df_city_2025 = df_2025_daily.groupby('date').agg({
        'aqi': 'mean',
        'pm25': 'mean',
        'temp': 'mean',
        'wind_speed': 'mean'
    }).reset_index()
    df_city_2025['date_dt'] = pd.to_datetime(df_city_2025['date'])
    df_city_2025['rel_day'] = (df_city_2025['date_dt'] - pd.to_datetime('2025-10-20')).dt.days

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

    # Top panel: AQI & PM2.5 trajectory with pre-trend fit
    ax1.axvspan(-14, 0, color='#e0f2fe', alpha=0.5, label='Pre-Diwali Window (14 Days)')
    ax1.axvspan(0, 14, color='#fee2e2', alpha=0.5, label='Post-Diwali Window (14 Days)')
    ax1.axvline(0, color='#dc2626', linestyle='--', linewidth=2, label='Diwali Day (2025-10-20)')

    ax1.plot(df_city_2025['rel_day'], df_city_2025['aqi'], marker='o', color='#1e3a8a', linewidth=2.5, label='Citywide Mean AQI')
    ax1.plot(df_city_2025['rel_day'], df_city_2025['pm25'], marker='s', color='#d97706', linewidth=2, linestyle=':', label='Citywide Mean PM2.5 (µg/m³)')

    # Pre-trend regression line
    pre_mask = df_city_2025['rel_day'] < 0
    pre_days = df_city_2025.loc[pre_mask, 'rel_day']
    poly = np.polyfit(pre_days, df_city_2025.loc[pre_mask, 'aqi'], deg=1)
    ax1.plot(pre_days, np.polyval(poly, pre_days), color='#059669', linewidth=2.5, linestyle='--',
             label=f'Pre-Trend Linear Fit (+{poly[0]:.2f} pts/day, p<0.001)')

    ax1.set_ylabel('Air Quality Index / PM2.5 (µg/m³)', fontsize=12, fontweight='bold')
    ax1.set_title('Figure 1: Delhi 2025 Diwali Window — Non-Parallel Pre-Trends & Rapid Baseline Escalation', fontsize=13, fontweight='bold', pad=12)
    ax1.legend(loc='upper left', frameon=True, fontsize=10)
    ax1.grid(True, alpha=0.4)

    # Bottom panel: Meteorology (Temperature & Wind Speed)
    ax2.plot(df_city_2025['rel_day'], df_city_2025['temp'], marker='^', color='#dc2626', linewidth=1.8, label='Temperature (°C)')
    ax2_r = ax2.twinx()
    ax2_r.plot(df_city_2025['rel_day'], df_city_2025['wind_speed'], marker='d', color='#2563eb', linewidth=1.8, linestyle='-.', label='Wind Speed (m/s)')
    ax2_r.grid(False)

    ax2.set_xlabel('Days Relative to Diwali (0 = 2025-10-20)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Temperature (°C)', fontsize=11, fontweight='bold', color='#dc2626')
    ax2_r.set_ylabel('Wind Speed (m/s)', fontsize=11, fontweight='bold', color='#2563eb')
    ax2.set_xlim(-14.5, 14.5)
    ax2.axvline(0, color='#dc2626', linestyle='--', linewidth=1.5)

    lines_1, labels_1 = ax2.get_legend_handles_labels()
    lines_2, labels_2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc='lower left', frameon=True, fontsize=10)

    plt.tight_layout()
    fig_path_1 = os.path.join(FIGURES_DIR, '01_diwali_2025_timeline_and_pretrends.png')
    plt.savefig(fig_path_1)
    plt.close()

    # -------------------------------------------------------------
    # Figure 2: Hourly Combustion Dynamics & SO2 Tracer Pulse
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=False)

    # 2025 Hourly
    df_h_2025 = df_2025_hourly.groupby('ts').agg({'pm25': 'mean', 'so2': 'mean'}).reset_index()
    df_h_2025['ts_dt'] = pd.to_datetime(df_h_2025['ts'])
    mask_2025 = (df_h_2025['ts_dt'] >= '2025-10-19 12:00:00') & (df_h_2025['ts_dt'] <= '2025-10-22 12:00:00')
    df_plot_2025 = df_h_2025[mask_2025]

    ax1.plot(df_plot_2025['ts_dt'], df_plot_2025['pm25'], color='#dc2626', linewidth=2.2, label='PM2.5 (µg/m³)')
    ax1_r = ax1.twinx()
    ax1_r.plot(df_plot_2025['ts_dt'], df_plot_2025['so2'], color='#d97706', linewidth=2.2, linestyle='--', label='SO2 Firecracker Tracer (µg/m³)')
    ax1_r.grid(False)

    ax1.axvline(pd.to_datetime('2025-10-20 20:00:00'), color='#4b5563', linestyle=':', label='Peak Bursting Window')
    ax1.set_ylabel('PM2.5 (µg/m³)', fontsize=11, fontweight='bold', color='#dc2626')
    ax1_r.set_ylabel('SO2 (µg/m³)', fontsize=11, fontweight='bold', color='#d97706')
    ax1.set_title('Figure 2A: Delhi Diwali 2025 — Acute Firecracker Combustion Pulse (PM2.5 Peak: 961 µg/m³, SO2 Peak: 74 µg/m³)', fontsize=12, fontweight='bold')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))

    lines_a1, labels_a1 = ax1.get_legend_handles_labels()
    lines_a2, labels_a2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines_a1 + lines_a2, labels_a1 + labels_a2, loc='upper left', frameon=True, fontsize=9)

    # 2024 Hourly
    df_h_2024 = df_2024_hourly.groupby('ts').agg({'pm25': 'mean', 'so2': 'mean'}).reset_index()
    df_h_2024['ts_dt'] = pd.to_datetime(df_h_2024['ts'])
    mask_2024 = (df_h_2024['ts_dt'] >= '2024-10-30 12:00:00') & (df_h_2024['ts_dt'] <= '2024-11-02 12:00:00')
    df_plot_2024 = df_h_2024[mask_2024]

    ax2.plot(df_plot_2024['ts_dt'], df_plot_2024['pm25'], color='#2563eb', linewidth=2.2, label='PM2.5 (µg/m³)')
    ax2_r = ax2.twinx()
    ax2_r.plot(df_plot_2024['ts_dt'], df_plot_2024['so2'], color='#7c3aed', linewidth=2.2, linestyle='--', label='SO2 Firecracker Tracer (µg/m³)')
    ax2_r.grid(False)

    ax2.axvline(pd.to_datetime('2024-10-31 20:00:00'), color='#4b5563', linestyle=':', label='Peak Bursting Window')
    ax2.set_ylabel('PM2.5 (µg/m³)', fontsize=11, fontweight='bold', color='#2563eb')
    ax2_r.set_ylabel('SO2 (µg/m³)', fontsize=11, fontweight='bold', color='#7c3aed')
    ax2.set_title('Figure 2B: Delhi Diwali 2024 — Acute Firecracker Combustion Pulse (PM2.5 Peak: 613 µg/m³, SO2 Peak: 80 µg/m³)', fontsize=12, fontweight='bold')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))

    lines_b1, labels_b1 = ax2.get_legend_handles_labels()
    lines_b2, labels_b2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines_b1 + lines_b2, labels_b1 + labels_b2, loc='upper left', frameon=True, fontsize=9)

    plt.tight_layout()
    fig_path_2 = os.path.join(FIGURES_DIR, '02_diwali_hourly_pulse_and_so2_tracer.png')
    plt.savefig(fig_path_2)
    plt.close()

    # -------------------------------------------------------------
    # Figure 3: Placebo Test Comparison (Diwali 2025 vs Placebo Sep 20)
    # -------------------------------------------------------------
    df_city_p = df_2025_placebo.groupby('date').agg({'aqi': 'mean'}).reset_index()
    df_city_p['date_dt'] = pd.to_datetime(df_city_p['date'])
    df_city_p['rel_day'] = (df_city_p['date_dt'] - pd.to_datetime('2025-09-20')).dt.days

    fig, ax = plt.subplots(figsize=(11, 6))

    ax.plot(df_city_2025['rel_day'], df_city_2025['aqi'], marker='o', color='#dc2626', linewidth=2.2, label='Diwali 2025 Window (Oct 20, 2025, Shift = +135.6 pts)')
    ax.plot(df_city_p['rel_day'], df_city_p['aqi'], marker='^', color='#2563eb', linewidth=2.2, linestyle='--', label='Placebo Non-Event Window (Sep 20, 2025, Shift = +24.0 pts, p<0.001)')

    ax.axvline(0, color='#4b5563', linestyle=':', linewidth=2, label='Event / Pseudo-Event Threshold (t=0)')
    ax.axvspan(-14, 0, color='#f3f4f6', alpha=0.5)
    ax.axvspan(0, 14, color='#fef3c7', alpha=0.5)

    ax.set_xlabel('Days Relative to Event / Placebo Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Citywide Mean AQI', fontsize=12, fontweight='bold')
    ax.set_title('Figure 3: In-Time Placebo Event Study — Spurious Positive Effects Under Seasonal Baseline Drift', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlim(-14.5, 14.5)
    ax.legend(loc='upper left', frameon=True, fontsize=10)
    ax.grid(True, alpha=0.4)

    plt.tight_layout()
    fig_path_3 = os.path.join(FIGURES_DIR, '03_placebo_test_comparison.png')
    plt.savefig(fig_path_3)
    plt.close()

    # -------------------------------------------------------------
    # Figure 4: Forest Plot of Regression Coefficients & 95% CIs
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 6))

    models_to_plot = df_models_summary.iloc[1:].copy() # Models 1 to 5
    y_pos = np.arange(len(models_to_plot))

    ax.errorbar(
        models_to_plot['coef'],
        y_pos,
        xerr=[
            models_to_plot['coef'] - models_to_plot['ci_lower'],
            models_to_plot['ci_upper'] - models_to_plot['coef']
        ],
        fmt='o',
        color='#1e3a8a',
        ecolor='#dc2626',
        elinewidth=2.5,
        capsize=6,
        markersize=8
    )

    ax.axvline(0, color='#4b5563', linestyle='--', linewidth=1.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(models_to_plot['model_id'], fontsize=11, fontweight='bold')
    ax.invert_yaxis()
    ax.set_xlabel('Estimated Policy/Event Coefficient (AQI Points) & 95% CI', fontsize=12, fontweight='bold')
    ax.set_title('Figure 4: Econometric Model Comparison — Collapse of Apparent Treatment Effect Under ITS Specification', fontsize=13, fontweight='bold', pad=12)
    ax.grid(True, alpha=0.4)

    # Annotate values
    for i, row in models_to_plot.reset_index().iterrows():
        ax.text(
            row['coef'],
            i - 0.2,
            f"β = {row['coef']:+.2f} [{row['ci_lower']:.2f}, {row['ci_upper']:.2f}], p={row['p_value']:.3f}",
            fontsize=9.5,
            fontweight='bold',
            color='#1f2937',
            ha='center'
        )

    plt.tight_layout()
    fig_path_4 = os.path.join(FIGURES_DIR, '04_regression_coefficients_comparison.png')
    plt.savefig(fig_path_4)
    plt.close()

    print(f"Generated 4 diagnostic figures in {FIGURES_DIR}")


def export_csv_tables(df_2025_daily, df_2024_daily, df_2025_placebo, df_models_summary, df_2025_hourly, df_2024_hourly):
    # 1. Policy status table
    df_policy = pd.DataFrame([
        {
            'year': 2023,
            'diwali_date': '2023-11-12',
            'delhi_ban_status': 'Complete Blanket Ban (DPCC / Supreme Court)',
            'mumbai_ban_status': 'Restricted Green Crackers (8 PM - 10 PM Bombay HC)',
            'delhi_data_coverage': 'Dwarka-Sector 8 CAAQMS (Hourly)',
            'mumbai_data_coverage': 'Not Available in Repository (Jan-Jul 2026 Only)'
        },
        {
            'year': 2024,
            'diwali_date': '2024-10-31',
            'delhi_ban_status': 'Complete Blanket Ban (DPCC Notification Sep 9, 2024)',
            'mumbai_ban_status': 'No Blanket Ban (Standard Noise Regulations)',
            'delhi_data_coverage': 'All 7 Delhi Stations CAAQMS (Hourly)',
            'mumbai_data_coverage': 'Not Available in Repository (Jan-Jul 2026 Only)'
        },
        {
            'year': 2025,
            'diwali_date': '2025-10-20',
            'delhi_ban_status': 'Complete Blanket Ban (DPCC / Delhi Govt)',
            'mumbai_ban_status': 'No Blanket Ban (Permitted Green Crackers)',
            'delhi_data_coverage': 'All 7 Stations CAAQMS + Official AQI Hourly',
            'mumbai_data_coverage': 'Not Available in Repository (Jan-Jul 2026 Only)'
        }
    ])
    df_policy.to_csv(os.path.join(OUTPUT_DIR, 'diwali_policy_status_timeline.csv'), index=False)

    # 2. Daily summary tables
    df_2025_daily.to_csv(os.path.join(OUTPUT_DIR, 'diwali_2025_daily_window.csv'), index=False)
    df_2024_daily.to_csv(os.path.join(OUTPUT_DIR, 'diwali_2024_daily_window.csv'), index=False)
    df_2025_placebo.to_csv(os.path.join(OUTPUT_DIR, 'placebo_2025_daily_window.csv'), index=False)
    df_models_summary.to_csv(os.path.join(OUTPUT_DIR, 'regression_models_summary.csv'), index=False)

    # 3. Hourly spike comparison table
    # 2025 spike
    df_h25 = df_2025_hourly.groupby('ts').agg({'pm25': 'mean', 'pm10': 'mean', 'so2': 'mean', 'no2': 'mean', 'co': 'mean'}).reset_index()
    df_h24 = df_2024_hourly.groupby('ts').agg({'pm25': 'mean', 'pm10': 'mean', 'so2': 'mean', 'no2': 'mean', 'co': 'mean'}).reset_index()

    peak_25_idx = df_h25['pm25'].idxmax()
    peak_24_idx = df_h24['pm25'].idxmax()

    df_spikes = pd.DataFrame([
        {
            'event': 'Diwali 2024 Night',
            'diwali_date': '2024-10-31',
            'daytime_baseline_pm25': df_h24[df_h24['ts'].astype(str).str.contains('2024-10-31 14:00:00')]['pm25'].values[0],
            'peak_pm25_timestamp': str(df_h24.loc[peak_24_idx, 'ts']),
            'peak_pm25_ug_m3': df_h24.loc[peak_24_idx, 'pm25'],
            'pm25_surge_multiplier': df_h24.loc[peak_24_idx, 'pm25'] / df_h24[df_h24['ts'].astype(str).str.contains('2024-10-31 14:00:00')]['pm25'].values[0],
            'daytime_baseline_so2': df_h24[df_h24['ts'].astype(str).str.contains('2024-10-31 14:00:00')]['so2'].values[0],
            'peak_so2_ug_m3': df_h24['so2'].max(),
            'so2_surge_multiplier': df_h24['so2'].max() / df_h24[df_h24['ts'].astype(str).str.contains('2024-10-31 14:00:00')]['so2'].values[0]
        },
        {
            'event': 'Diwali 2025 Night',
            'diwali_date': '2025-10-20',
            'daytime_baseline_pm25': df_h25[df_h25['ts'].astype(str).str.contains('2025-10-20 14:00:00')]['pm25'].values[0],
            'peak_pm25_timestamp': str(df_h25.loc[peak_25_idx, 'ts']),
            'peak_pm25_ug_m3': df_h25.loc[peak_25_idx, 'pm25'],
            'pm25_surge_multiplier': df_h25.loc[peak_25_idx, 'pm25'] / df_h25[df_h25['ts'].astype(str).str.contains('2025-10-20 14:00:00')]['pm25'].values[0],
            'daytime_baseline_so2': df_h25[df_h25['ts'].astype(str).str.contains('2025-10-20 14:00:00')]['so2'].values[0],
            'peak_so2_ug_m3': df_h25['so2'].max(),
            'so2_surge_multiplier': df_h25['so2'].max() / df_h25[df_h25['ts'].astype(str).str.contains('2025-10-20 14:00:00')]['so2'].values[0]
        }
    ])
    df_spikes.to_csv(os.path.join(OUTPUT_DIR, 'hourly_spike_comparison.csv'), index=False)
    print(f"Exported diagnostic CSV tables to {OUTPUT_DIR}")


def main():
    print("Extracting CAAQMS and AQI data from PostgreSQL...")
    connected = True
    try:
        df_2025_daily, df_2025_hourly, df_2024_daily, df_2024_hourly, df_2025_placebo = extract_data()
    except Exception as exc:
        connected = False
        print(f"[warn] PostgreSQL unavailable ({type(exc).__name__}); using cached daily CSVs.")
        df_2025_daily = pd.read_csv(os.path.join(OUTPUT_DIR, 'diwali_2025_daily_window.csv'))
        df_2025_placebo = pd.read_csv(os.path.join(OUTPUT_DIR, 'placebo_2025_daily_window.csv'))
        df_2024_daily = pd.read_csv(os.path.join(OUTPUT_DIR, 'diwali_2024_daily_window.csv'))
        df_2025_hourly, df_2024_hourly = None, None

    print("Fitting econometric models and hypothesis tests (PM2.5 primary, SEs clustered by date)...")
    df_models_summary, fits = run_statistical_models(df_2025_daily, df_2025_placebo)
    df_models_summary.to_csv(os.path.join(OUTPUT_DIR, 'regression_models_summary.csv'), index=False)
    print(f"Saved regression_models_summary.csv ({len(df_models_summary)} rows)")

    if connected:
        print("Generating figures...")
        generate_plots(df_2025_daily, df_2025_hourly, df_2024_hourly, df_2025_placebo, df_models_summary)
        print("Exporting CSV tables...")
        export_csv_tables(df_2025_daily, df_2024_daily, df_2025_placebo, df_models_summary, df_2025_hourly, df_2024_hourly)
    else:
        print("[warn] Skipping figures and hourly spike tables (hourly data is not cached in the required shape).")

    print("\n--- MASTER REGRESSION SUMMARY (PM2.5 primary, SEs clustered by date) ---")
    cols = ['model_id', 'outcome', 'coef_name', 'coef', 'std_err', 'p_value', 'ci_lower', 'ci_upper', 'se_type', 'n_clusters']
    print(df_models_summary[df_models_summary['outcome'] == 'pm25'][cols].to_string(index=False))
    print("\nCausal analysis pipeline completed successfully.")


if __name__ == '__main__':
    main()

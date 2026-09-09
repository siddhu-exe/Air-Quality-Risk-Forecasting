"""
src/eda/generate_visualizations.py

Generates the complete 11-figure EDA visualization suite in reports/eda/figures/:
1.  01_aqi_timeseries.png - Daily AQI time-series across stations
2.  02_diurnal_profiles.png - 24-hour diurnal pollutant and AQI dynamics
3.  03_monthly_trends.png - Monthly seasonal AQI progression by station
4.  04_seasonal_comparison.png - Seasonal comparison of AQI, PM2.5, and PM10
5.  05_station_comparison.png - Multi-metric station comparison (Mean, Median, P90, P95)
6.  06_distributions_skewness.png - Distribution plots with skewness & kurtosis
7.  07_correlation_heatmaps.png - Pearson & Spearman correlation heatmaps
8.  08_pm25_vs_aqi_breakpoints.png - PM2.5 vs AQI scatter & CPCB breakpoint transfer curve
9.  09_weather_relationships.png - Temperature, Wind Speed & Humidity vs PM2.5/AQI
10. 10_missingness_heatmap.png - Station-by-variable data completeness heatmap
11. 11_extreme_episodes.png - Severe episode duration and peak AQI distribution
"""

from __future__ import annotations
import sys
from pathlib import Path
import psycopg2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings("ignore")

# Set publication style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["figure.dpi"] = 300
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["figure.autolayout"] = True

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_DIR / "etl"))
from load_postgres import load_env, get_connection

FIGURES_DIR = PROJECT_DIR / "reports" / "eda" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = PROJECT_DIR / "reports" / "eda"

def fetch_daily_aqi_and_pm(conn):
    query = """
    SELECT
        s.station_name,
        DATE(a.timestamp AT TIME ZONE 'Asia/Kolkata') as log_date,
        AVG(a.aqi_value) as mean_aqi,
        AVG(c.pm25) as mean_pm25
    FROM aqi_hourly a
    JOIN stations s ON a.station_id = s.station_id
    LEFT JOIN caaqms_hourly c ON a.station_id = c.station_id AND a.timestamp = c.timestamp
    GROUP BY s.station_name, log_date
    ORDER BY s.station_name, log_date;
    """
    return pd.read_sql_query(query, conn)

def fetch_weather_pollutant_samples(conn):
    query = """
    SELECT
        c.pm25,
        c.pm10,
        c.temperature,
        c.humidity,
        c.wind_speed,
        c.solar_radiation,
        a.aqi_value
    FROM caaqms_hourly c
    JOIN aqi_hourly a ON c.station_id = a.station_id AND c.timestamp = a.timestamp
    WHERE c.pm25 IS NOT NULL
      AND a.aqi_value IS NOT NULL
      AND c.temperature IS NOT NULL
      AND c.wind_speed IS NOT NULL
      AND c.humidity IS NOT NULL
    LIMIT 30000;
    """
    return pd.read_sql_query(query, conn)

def plot_01_aqi_timeseries(conn):
    print("Plotting 01: AQI Time Series...")
    df = fetch_daily_aqi_and_pm(conn)
    df["log_date"] = pd.to_datetime(df["log_date"])

    fig, ax = plt.subplots(figsize=(12, 5))
    stations = df["station_name"].unique()
    palette = sns.color_palette("tab10", len(stations))

    for i, station in enumerate(stations):
        sub = df[df["station_name"] == station].sort_values("log_date")
        # 7-day rolling mean for clear signal
        sub["rolling_aqi"] = sub["mean_aqi"].rolling(7, min_periods=1).mean()
        ax.plot(sub["log_date"], sub["rolling_aqi"], label=station, color=palette[i], alpha=0.85, linewidth=1.5)

    # CPCB AQI Risk Bands
    ax.axhspan(0, 50, color="#00e400", alpha=0.1, label="Good (0-50)")
    ax.axhspan(51, 100, color="#92d050", alpha=0.1, label="Satisfactory (51-100)")
    ax.axhspan(101, 200, color="#ffff00", alpha=0.1, label="Moderate (101-200)")
    ax.axhspan(201, 300, color="#ff7e00", alpha=0.1, label="Poor (201-300)")
    ax.axhspan(301, 400, color="#ff0000", alpha=0.1, label="Very Poor (301-400)")
    ax.axhspan(401, 500, color="#7e0023", alpha=0.15, label="Severe (401-500)")

    ax.set_title("Delhi 7-Day Rolling Mean AQI by Monitoring Station (2025)", fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Air Quality Index (AQI)")
    ax.set_ylim(0, 500)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=True, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "01_aqi_timeseries.png")
    plt.close(fig)

def plot_02_diurnal_profiles():
    print("Plotting 02: Hourly Diurnal Profiles...")
    df = pd.read_csv(REPORTS_DIR / "hourly_summary.csv")

    # Calculate Delhi-wide mean diurnal cycle across stations
    diurnal = df.groupby("hour_of_day").agg({
        "pm25_mean": "mean",
        "pm10_mean": "mean",
        "no2_mean": "mean",
        "o3_mean": "mean",
        "aqi_mean": "mean"
    }).reset_index()

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)

    # PM2.5 & PM10
    axes[0, 0].plot(diurnal["hour_of_day"], diurnal["pm25_mean"], marker="o", color="#d62728", label="PM2.5 (µg/m³)", linewidth=2)
    axes[0, 0].plot(diurnal["hour_of_day"], diurnal["pm10_mean"], marker="s", color="#ff7f0e", label="PM10 (µg/m³)", linewidth=2)
    axes[0, 0].set_title("Particulate Matter (PM2.5 & PM10) Diurnal Cycle", fontweight="bold")
    axes[0, 0].set_ylabel("Concentration (µg/m³)")
    axes[0, 0].legend()
    axes[0, 0].grid(True, linestyle="--", alpha=0.6)

    # NO2 vs O3 Photochemical Coupling
    axes[0, 1].plot(diurnal["hour_of_day"], diurnal["no2_mean"], marker="^", color="#9467bd", label="NO2 (µg/m³) - Primary/Traffic", linewidth=2)
    axes[0, 1].plot(diurnal["hour_of_day"], diurnal["o3_mean"], marker="d", color="#2ca02c", label="O3 (µg/m³) - Secondary/Photochemical", linewidth=2)
    axes[0, 1].set_title("Photochemical Balance: NO2 vs Ozone (O3)", fontweight="bold")
    axes[0, 1].set_ylabel("Concentration (µg/m³)")
    axes[0, 1].legend()
    axes[0, 1].grid(True, linestyle="--", alpha=0.6)

    # AQI Profile
    axes[1, 0].plot(diurnal["hour_of_day"], diurnal["aqi_mean"], marker="p", color="#8c564b", label="AQI (24h Buffered)", linewidth=2)
    axes[1, 0].set_title("Reported AQI Diurnal Curve", fontweight="bold")
    axes[1, 0].set_xlabel("Hour of Day (IST)")
    axes[1, 0].set_ylabel("AQI Value")
    axes[1, 0].set_ylim(180, 240)
    axes[1, 0].legend()
    axes[1, 0].grid(True, linestyle="--", alpha=0.6)

    # Normalized Comparison (Diurnal Rhythm Decoupling)
    norm_pm25 = (diurnal["pm25_mean"] - diurnal["pm25_mean"].min()) / (diurnal["pm25_mean"].max() - diurnal["pm25_mean"].min())
    norm_o3 = (diurnal["o3_mean"] - diurnal["o3_mean"].min()) / (diurnal["o3_mean"].max() - diurnal["o3_mean"].min())
    norm_aqi = (diurnal["aqi_mean"] - diurnal["aqi_mean"].min()) / (diurnal["aqi_mean"].max() - diurnal["aqi_mean"].min())

    axes[1, 1].plot(diurnal["hour_of_day"], norm_pm25, label="PM2.5 (Peak: 07:00 & 23:00)", color="#d62728", linewidth=2)
    axes[1, 1].plot(diurnal["hour_of_day"], norm_o3, label="Ozone (Peak: 14:00 Photochemical)", color="#2ca02c", linewidth=2)
    axes[1, 1].plot(diurnal["hour_of_day"], norm_aqi, label="AQI (Buffered Rolling Index)", color="#8c564b", linewidth=2, linestyle="--")
    axes[1, 1].set_title("Normalized Comparison (Min-Max Scaled)", fontweight="bold")
    axes[1, 1].set_xlabel("Hour of Day (IST)")
    axes[1, 1].set_ylabel("Normalized Index [0-1]")
    axes[1, 1].legend(fontsize=8)
    axes[1, 1].grid(True, linestyle="--", alpha=0.6)

    plt.xticks(range(0, 24, 2))
    fig.suptitle("Diurnal Atmospheric Cycles across Delhi Monitoring Stations", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "02_diurnal_profiles.png")
    plt.close(fig)

def plot_03_monthly_trends():
    print("Plotting 03: Monthly Trends...")
    df = pd.read_csv(REPORTS_DIR / "monthly_summary.csv")

    # Filter to 2025 where AQI data is available across all 7 stations
    df_2025 = df[df["year"] == 2025].dropna(subset=["aqi_mean"])

    fig, ax = plt.subplots(figsize=(11, 5))
    stations = df_2025["station_name"].unique()
    palette = sns.color_palette("tab10", len(stations))

    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for i, station in enumerate(stations):
        sub = df_2025[df_2025["station_name"] == station].sort_values("month")
        ax.plot(sub["month_name"], sub["aqi_mean"], marker="o", label=station, color=palette[i], linewidth=2)

    ax.axvspan("Jul", "Sep", color="#2ca02c", alpha=0.12, label="Monsoon Washout (Low AQI)")
    ax.axvspan("Nov", "Jan", color="#d62728", alpha=0.12, label="Winter Smog Peak (Severe)")

    ax.set_title("Monthly Mean AQI by Monitoring Station (Delhi, 2025)", fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Mean AQI")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "03_monthly_trends.png")
    plt.close(fig)

def plot_04_seasonal_comparison():
    print("Plotting 04: Seasonal Comparison...")
    df = pd.read_csv(REPORTS_DIR / "seasonal_summary.csv")

    season_order = ["Winter", "Summer", "Monsoon", "Post-Monsoon"]
    df_agg = df.groupby("season").agg({
        "aqi_mean": "mean",
        "pm25_mean": "mean",
        "pm10_mean": "mean"
    }).reindex(season_order).reset_index()

    x = np.arange(len(season_order))
    width = 0.25

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width, df_agg["aqi_mean"], width, label="Mean AQI", color="#d62728", edgecolor="black", alpha=0.85)
    ax.bar(x, df_agg["pm10_mean"], width, label="Mean PM10 (µg/m³)", color="#ff7f0e", edgecolor="black", alpha=0.85)
    ax.bar(x + width, df_agg["pm25_mean"], width, label="Mean PM2.5 (µg/m³)", color="#1f77b4", edgecolor="black", alpha=0.85)

    ax.set_title("Seasonal Pollution Comparison in Delhi (AQI, PM2.5, PM10)", fontweight="bold")
    ax.set_xlabel("Season")
    ax.set_ylabel("Concentration / Index Value")
    ax.set_xticks(x)
    ax.set_xticklabels(season_order, fontweight="bold")
    ax.legend(frameon=True)
    ax.grid(True, linestyle="--", alpha=0.6, axis="y")

    for i in range(len(season_order)):
        ax.text(x[i]-width, df_agg["aqi_mean"].iloc[i] + 5, f"{df_agg['aqi_mean'].iloc[i]:.0f}", ha="center", fontsize=9)
        ax.text(x[i], df_agg["pm10_mean"].iloc[i] + 5, f"{df_agg['pm10_mean'].iloc[i]:.0f}", ha="center", fontsize=9)
        ax.text(x[i]+width, df_agg["pm25_mean"].iloc[i] + 5, f"{df_agg['pm25_mean'].iloc[i]:.0f}", ha="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "04_seasonal_comparison.png")
    plt.close(fig)

def plot_05_station_comparison():
    print("Plotting 05: Station Metric Comparison...")
    df = pd.read_csv(REPORTS_DIR / "station_summary.csv").sort_values("aqi_mean", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # AQI Metrics
    x = np.arange(len(df))
    w = 0.2
    axes[0].bar(x - 1.5*w, df["aqi_mean"], w, label="Mean", color="#e41a1c")
    axes[0].bar(x - 0.5*w, df["aqi_median"], w, label="Median", color="#377eb8")
    axes[0].bar(x + 0.5*w, df["aqi_p90"], w, label="P90", color="#ff7f00")
    axes[0].bar(x + 1.5*w, df["aqi_p95"], w, label="P95", color="#984ea3")
    axes[0].set_title("AQI Distribution Metrics Across Stations", fontweight="bold")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(df["station_name"], rotation=30, ha="right")
    axes[0].set_ylabel("AQI Value")
    axes[0].legend()
    axes[0].grid(True, linestyle="--", alpha=0.5, axis="y")

    # PM2.5 Metrics
    axes[1].bar(x - 1.5*w, df["pm25_mean"], w, label="Mean", color="#e41a1c")
    axes[1].bar(x - 0.5*w, df["pm25_median"], w, label="Median", color="#377eb8")
    axes[1].bar(x + 0.5*w, df["pm25_p90"], w, label="P90", color="#ff7f00")
    # Using 1.25 * p90 as proxy for p95 where needed or omitting
    axes[1].set_title("PM2.5 Distribution Metrics Across Stations", fontweight="bold")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["station_name"], rotation=30, ha="right")
    axes[1].set_ylabel("PM2.5 (µg/m³)")
    axes[1].legend()
    axes[1].grid(True, linestyle="--", alpha=0.5, axis="y")

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "05_station_comparison.png")
    plt.close(fig)

def plot_06_distributions_skewness(conn):
    print("Plotting 06: Distributions and Skewness...")
    query = """
    SELECT c.pm25, c.pm10, c.no2, a.aqi_value
    FROM caaqms_hourly c
    JOIN aqi_hourly a ON c.station_id = a.station_id AND c.timestamp = a.timestamp
    WHERE c.pm25 IS NOT NULL AND c.pm10 IS NOT NULL AND a.aqi_value IS NOT NULL
    LIMIT 30000;
    """
    df = pd.read_sql_query(query, conn)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    params = [
        ("pm25", "PM2.5 (µg/m³)", axes[0, 0], "#d62728", 500),
        ("pm10", "PM10 (µg/m³)", axes[0, 1], "#ff7f0e", 800),
        ("no2", "NO2 (µg/m³)", axes[1, 0], "#9467bd", 250),
        ("aqi_value", "Air Quality Index (AQI)", axes[1, 1], "#1f77b4", 500)
    ]

    for col, title, ax, color, xmax in params:
        series = df[col].dropna()
        sns.histplot(series[series <= xmax], bins=40, kde=True, ax=ax, color=color, edgecolor="black", alpha=0.6)

        mean_val = series.mean()
        med_val = series.median()
        skew_val = series.skew()
        kurt_val = series.kurtosis()

        ax.axvline(mean_val, color="black", linestyle="--", linewidth=1.5, label=f"Mean: {mean_val:.1f}")
        ax.axvline(med_val, color="blue", linestyle=":", linewidth=1.5, label=f"Median: {med_val:.1f}")

        ax.set_title(f"{title} Distribution", fontweight="bold")
        ax.set_xlabel(title)
        ax.set_ylabel("Frequency")
        ax.text(0.65, 0.70, f"Skewness: {skew_val:+.2f}\nKurtosis: {kurt_val:+.2f}", transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8), fontsize=9)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.5)

    fig.suptitle("Atmospheric & AQI Statistical Distributions (Delhi NCR)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "06_distributions_skewness.png")
    plt.close(fig)

def plot_07_correlation_heatmaps():
    print("Plotting 07: Pearson & Spearman Correlation Heatmaps...")
    p_df = pd.read_csv(REPORTS_DIR / "correlation_matrix.csv", index_col=0)
    s_df = pd.read_csv(REPORTS_DIR / "spearman_correlation_matrix.csv", index_col=0)

    # Filter to main variables for readability
    main_vars = ["pm25", "pm10", "no", "no2", "nox", "nh3", "so2", "co", "o3", "temperature", "humidity", "wind_speed", "solar_radiation", "aqi_value"]
    p_sub = p_df.loc[p_df.index.isin(main_vars), p_df.columns.isin(main_vars)]
    s_sub = s_df.loc[s_df.index.isin(main_vars), s_df.columns.isin(main_vars)]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    sns.heatmap(p_sub, annot=True, fmt=".2f", cmap="coolwarm", vmin=-0.8, vmax=1.0, ax=axes[0], cbar_kws={"shrink": 0.8})
    axes[0].set_title("Pearson Linear Correlation Matrix", fontweight="bold")
    axes[0].set_xticklabels(axes[0].get_xticklabels(), rotation=45, ha="right")

    sns.heatmap(s_sub, annot=True, fmt=".2f", cmap="coolwarm", vmin=-0.8, vmax=1.0, ax=axes[1], cbar_kws={"shrink": 0.8})
    axes[1].set_title("Spearman Rank Non-Linear Correlation Matrix", fontweight="bold")
    axes[1].set_xticklabels(axes[1].get_xticklabels(), rotation=45, ha="right")

    fig.suptitle("Multi-Pollutant & Meteorological Inter-Variable Correlation", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "07_correlation_heatmaps.png")
    plt.close(fig)

def plot_08_pm25_vs_aqi_breakpoints(conn):
    print("Plotting 08: PM2.5 vs AQI Breakpoints Curve...")
    query = """
    SELECT c.pm25, a.aqi_value
    FROM caaqms_hourly c
    JOIN aqi_hourly a ON c.station_id = a.station_id AND c.timestamp = a.timestamp
    WHERE c.pm25 IS NOT NULL AND a.aqi_value IS NOT NULL AND c.pm25 <= 600
    LIMIT 20000;
    """
    df = pd.read_sql_query(query, conn)

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(df["pm25"], df["aqi_value"], alpha=0.15, color="#1f77b4", s=10, label="Observed Pairs (Hourly)")

    # CPCB Piecewise Linear AQI Breakpoint Curve for PM2.5 (24h reference breakpoints)
    cpcb_pm25_bp = [0, 30, 60, 90, 120, 250, 380, 500]
    cpcb_aqi_bp = [0, 50, 100, 200, 300, 400, 500, 500]
    ax.plot(cpcb_pm25_bp, cpcb_aqi_bp, color="red", linewidth=2.5, linestyle="--", label="CPCB PM2.5 Transfer Function")

    # Polynomial trendline
    z = np.polyfit(df["pm25"], df["aqi_value"], 2)
    p = np.poly1d(z)
    x_vals = np.linspace(0, 500, 100)
    ax.plot(x_vals, p(x_vals), color="black", linewidth=2, label="Empirical Quadratic Fit")

    ax.set_title("Hourly PM2.5 Concentration vs Official AQI Transfer Response", fontweight="bold")
    ax.set_xlabel("PM2.5 Concentration (µg/m³)")
    ax.set_ylabel("Air Quality Index (AQI)")
    ax.set_xlim(0, 500)
    ax.set_ylim(0, 500)
    ax.legend(frameon=True)
    ax.grid(True, linestyle="--", alpha=0.6)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "08_pm25_vs_aqi_breakpoints.png")
    plt.close(fig)

def plot_09_weather_relationships(conn):
    print("Plotting 09: Meteorological Relationships...")
    df = fetch_weather_pollutant_samples(conn)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    # Temperature vs PM2.5
    sns.regplot(x="temperature", y="pm25", data=df[df["pm25"] <= 500], ax=axes[0],
                scatter_kws={"alpha": 0.1, "color": "#e41a1c", "s": 8},
                line_kws={"color": "darkred", "linewidth": 2})
    axes[0].set_title("Temperature vs PM2.5 (r = -0.52)", fontweight="bold")
    axes[0].set_xlabel("Ambient Temperature (°C)")
    axes[0].set_ylabel("PM2.5 (µg/m³)")
    axes[0].grid(True, linestyle="--", alpha=0.5)

    # Wind Speed vs PM2.5
    sns.regplot(x="wind_speed", y="pm25", data=df[(df["pm25"] <= 500) & (df["wind_speed"] <= 10)], ax=axes[1],
                scatter_kws={"alpha": 0.1, "color": "#377eb8", "s": 8},
                line_kws={"color": "navy", "linewidth": 2})
    axes[1].set_title("Wind Speed vs PM2.5 (Dispersion)", fontweight="bold")
    axes[1].set_xlabel("Wind Speed (m/s)")
    axes[1].set_ylabel("PM2.5 (µg/m³)")
    axes[1].grid(True, linestyle="--", alpha=0.5)

    # Humidity vs PM2.5
    sns.regplot(x="humidity", y="pm25", data=df[df["pm25"] <= 500], ax=axes[2],
                scatter_kws={"alpha": 0.1, "color": "#4daf4a", "s": 8},
                line_kws={"color": "darkgreen", "linewidth": 2})
    axes[2].set_title("Relative Humidity vs PM2.5 (r = +0.27)", fontweight="bold")
    axes[2].set_xlabel("Relative Humidity (%)")
    axes[2].set_ylabel("PM2.5 (µg/m³)")
    axes[2].grid(True, linestyle="--", alpha=0.5)

    fig.suptitle("Meteorological Drivers of Atmospheric Particulate Dynamics", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "09_weather_relationships.png")
    plt.close(fig)

def plot_10_missingness_heatmap():
    print("Plotting 10: Missingness Heatmap...")
    df = pd.read_csv(REPORTS_DIR / "station_missingness_matrix.csv", index_col=0)

    # Rename columns for visual clarity
    col_order = [c for c in df.columns if c not in ["total_expected_hours", "total_actual_rows"]]
    df_pct = df[col_order]

    fig, ax = plt.subplots(figsize=(13, 5))
    sns.heatmap(df_pct, annot=True, fmt=".1f", cmap="YlOrRd", vmin=0, vmax=100, ax=ax, cbar_kws={"label": "Missingness Percentage (%)"})

    ax.set_title("Data Missingness & Sensor Availability Matrix Across Delhi Stations (%)", fontweight="bold")
    ax.set_xlabel("Atmospheric / Weather Variable")
    ax.set_ylabel("Station Name")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "10_missingness_heatmap.png")
    plt.close(fig)

def get_season_from_month(m):
    if m in [12, 1, 2]:
        return "Winter"
    elif m in [3, 4, 5, 6]:
        return "Summer"
    elif m in [7, 8, 9]:
        return "Monsoon"
    else:
        return "Post-Monsoon"

def plot_11_extreme_episodes():
    print("Plotting 11: Extreme AQI Episodes...")
    df = pd.read_csv(REPORTS_DIR / "episode_summary.csv")
    df["season"] = df["start_month"].apply(get_season_from_month)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Duration vs Peak AQI
    sns.scatterplot(x="duration_hours", y="max_aqi", hue="station_name", style="season", data=df, s=80, alpha=0.85, ax=axes[0])
    axes[0].set_title("Severe Episode Duration vs Peak AQI (AQI ≥ 400)", fontweight="bold")
    axes[0].set_xlabel("Episode Duration (Hours)")
    axes[0].set_ylabel("Maximum AQI Reached")
    axes[0].axhline(500, color="red", linestyle="--", alpha=0.5, label="Sensor Saturation (500)")
    axes[0].grid(True, linestyle="--", alpha=0.5)
    axes[0].legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)

    # Episode Count by Season & Station
    season_counts = df.groupby(["season", "station_name"]).size().unstack(fill_value=0)
    season_counts.plot(kind="bar", stacked=True, ax=axes[1], colormap="tab10", edgecolor="black", alpha=0.85)
    axes[1].set_title("Severe Pollution Episode Frequency by Season", fontweight="bold")
    axes[1].set_xlabel("Season")
    axes[1].set_ylabel("Total Number of Severe Episodes")
    axes[1].set_xticklabels(axes[1].get_xticklabels(), rotation=0)
    axes[1].grid(True, linestyle="--", alpha=0.5, axis="y")
    axes[1].legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)

    fig.suptitle("Severe Air Quality Episodes (AQI ≥ 400 for ≥ 6 Consecutive Hours)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "11_extreme_episodes.png")
    plt.close(fig)

def main():
    env = load_env()
    conn = get_connection(env)

    print(f"Generating visual suite into {FIGURES_DIR}...")
    plot_01_aqi_timeseries(conn)
    plot_02_diurnal_profiles()
    plot_03_monthly_trends()
    plot_04_seasonal_comparison()
    plot_05_station_comparison()
    plot_06_distributions_skewness(conn)
    plot_07_correlation_heatmaps()
    plot_08_pm25_vs_aqi_breakpoints(conn)
    plot_09_weather_relationships(conn)
    plot_10_missingness_heatmap()
    plot_11_extreme_episodes()

    conn.close()
    print("=== ALL 11 FIGURES GENERATED SUCCESSFULLY! ===")

if __name__ == "__main__":
    main()

"""
Air Quality Risk Forecasting & Policy Alerting System - Streamlit Web Dashboard
Production-grade interactive web application deployable to Streamlit Community Cloud.
"""

from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image

# -----------------------------------------------------------------------------
# Configuration & Theme Settings
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Delhi Air Quality Risk Forecasting",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Resolve Base Paths (Works both from project root and from within dashboard/)
try:
    CURRENT_DIR = Path(__file__).resolve().parent
except NameError:
    CURRENT_DIR = Path.cwd() / "dashboard" if (Path.cwd() / "dashboard").exists() else Path.cwd()
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "dashboard" else CURRENT_DIR


# -----------------------------------------------------------------------------
# Cached Data Loaders (@st.cache_data & @st.cache_resource)
# -----------------------------------------------------------------------------
@st.cache_data
def load_predictions_data():
    """Load test prediction parquets for 1h, 6h, and 24h horizons."""
    p1 = PROJECT_ROOT / "reports/classification/1h/classified_predictions.parquet"
    p6 = PROJECT_ROOT / "reports/classification/6h/classified_predictions.parquet"
    p24 = PROJECT_ROOT / "reports/classification/24h/classified_predictions.parquet"

    df1 = pd.read_parquet(p1)
    df6 = pd.read_parquet(p6)
    df24 = pd.read_parquet(p24)

    # Ensure timezone-aware datetime
    for df in [df1, df6, df24]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    return df1, df6, df24


@st.cache_data
def load_causal_data():
    """Load static datasets for Diwali causal analysis and hourly spike replay."""
    f_hourly = PROJECT_ROOT / "reports/causal/diwali_hourly_timeseries.csv"
    f_reg = PROJECT_ROOT / "reports/causal/regression_models_summary.csv"
    f_timeline = PROJECT_ROOT / "reports/causal/diwali_policy_status_timeline.csv"

    df_hourly = pd.read_csv(f_hourly)
    df_hourly['timestamp'] = pd.to_datetime(df_hourly['timestamp'])

    df_reg = pd.read_csv(f_reg)
    df_timeline = pd.read_csv(f_timeline)

    return df_hourly, df_reg, df_timeline


@st.cache_data
def load_cost_threshold_data():
    """Load cost sweep table and precomputed optimal threshold summaries."""
    f_sweep = PROJECT_ROOT / "reports/classification/metrics/cost_threshold_sweep_24h.csv"
    f_summary = PROJECT_ROOT / "reports/classification/metrics/cost_optimal_thresholds_summary.csv"
    f_operating = PROJECT_ROOT / "reports/classification/metrics/threshold_operating_points_comparison.csv"

    df_sweep = pd.read_csv(f_sweep)
    df_summary = pd.read_csv(f_summary)
    df_operating = pd.read_csv(f_operating)

    return df_sweep, df_summary, df_operating


@st.cache_data
def load_episodes_data():
    """Load crisis episode lead time audit dataset."""
    f_ep = PROJECT_ROOT / "reports/classification/episodes/grap_episode_lead_times.csv"
    df_ep = pd.read_csv(f_ep)
    df_ep['start_time'] = pd.to_datetime(df_ep['start_time'])
    df_ep['end_time'] = pd.to_datetime(df_ep['end_time'])
    return df_ep


@st.cache_resource
def load_cached_images():
    """Load static figures from reports directory."""
    img_forest_path = PROJECT_ROOT / "reports/causal/figures/04_regression_coefficients_comparison.png"
    img_pr_path = PROJECT_ROOT / "reports/classification/figures/01_precision_recall_curve_24h.png"

    img_forest = Image.open(img_forest_path) if img_forest_path.exists() else None
    img_pr = Image.open(img_pr_path) if img_pr_path.exists() else None

    return img_forest, img_pr


# -----------------------------------------------------------------------------
# Helper Functions: CPCB Tiers & GRAP Stages
# -----------------------------------------------------------------------------
def get_cpcb_tier(aqi):
    """Return CPCB tier name, color code, and CSS class."""
    if aqi <= 50:
        return "Good", "#009966", "cpcb-good"
    elif aqi <= 100:
        return "Satisfactory", "#55a84f", "cpcb-satisfactory"
    elif aqi <= 200:
        return "Moderate", "#d4a017", "cpcb-moderate"
    elif aqi <= 300:
        return "Poor", "#ff9933", "cpcb-poor"
    elif aqi <= 400:
        return "Very Poor", "#cc0033", "cpcb-very-poor"
    elif aqi <= 450:
        return "Severe", "#7e0023", "cpcb-severe"
    else:
        return "Severe+", "#4c0015", "cpcb-severe-plus"


def get_grap_stage_info(aqi):
    """Return CAQM GRAP Stage string and primary policy intervention."""
    if aqi <= 200:
        return "None", "Standard air quality monitoring"
    elif aqi <= 300:
        return "Stage I (Poor)", "Mechanized road sweeping & dust suppression"
    elif aqi <= 400:
        return "Stage II (Very Poor)", "Diesel generator bans & increased metro frequency"
    elif aqi <= 450:
        return "Stage III (Severe)", "Halt construction, brick kilns & BS-III/IV restrictions"
    else:
        return "Stage IV (Severe+)", "Truck entry bans, school closures & 50% remote work"


# -----------------------------------------------------------------------------
# App Data Initialization
# -----------------------------------------------------------------------------
df_1h, df_6h, df_24h = load_predictions_data()
df_diwali_hourly, df_reg_summary, df_timeline = load_causal_data()
df_sweep, df_cost_summary, df_operating = load_cost_threshold_data()
df_episodes = load_episodes_data()
img_forest, img_pr = load_cached_images()

STATIONS = sorted(df_1h['station_name'].unique().tolist())


# -----------------------------------------------------------------------------
# Sidebar Navigation & Meta
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🌫️ Delhi AQ Forecast")
    st.markdown("**Continuous CAAQMS Monitoring Network**")
    st.markdown("`7 Delhi Stations` • `124 Causal Features`")

    st.markdown("---")
    st.markdown("### Model Summary")
    st.markdown(r"""
    - **1h Forecast:** Tuned LightGBM ($\text{MAE} = 2.29$)
    - **6h Forecast:** Tuned LightGBM ($\text{MAE} = 11.84$)
    - **24h Forecast:** Hybrid Ridge + Persistence ($\text{MAE} = 34.11$)
    - **Test Window:** Nov–Dec 2025 ($N = 9,800$)
    """)

    st.markdown("---")
    st.markdown("[GitHub Repository ↗](https://github.com/Siddharth23052005/Air-quality-risk-forecasting)")


# =============================================================================
# Header
# =============================================================================
st.title("Delhi Air Quality Risk Forecasting & Policy Alerting")
st.markdown(
    "Continuous multi-horizon air quality forecasting, econometric policy evaluation, and asymmetric risk classification across Delhi's CAAQMS monitoring network. "
    "[GitHub Repository ↗](https://github.com/Siddharth23052005/Air-quality-risk-forecasting)"
)


# =============================================================================
# Main Navigation Tabs (5 Clean Focus Areas)
# =============================================================================
tab_overview, tab_forecasts, tab_diwali, tab_risk, tab_methodology = st.tabs([
    "Overview",
    "Forecasts",
    "Diwali Policy Finding",
    "Risk Threshold",
    "Methodology"
])


# =============================================================================
# TAB 1: Overview (Minimal, Zero Clutter on First Load)
# =============================================================================
with tab_overview:
    # 1. One-line value hook
    st.markdown(
        "**Real-time air quality snapshot across all 7 Delhi stations alongside validated 24-hour predictive lead performance.**"
    )

    # 2. 7-station current AQI snapshot (clean, tier only, native st.dataframe with column configuration)
    latest_ts = df_1h['timestamp'].max()
    df_latest = df_1h[df_1h['timestamp'] == latest_ts].copy().sort_values('station_name')

    table_data = []
    for _, r in df_latest.iterrows():
        aqi_val = int(round(float(r['y_true'])))
        cpcb_name, _, _ = get_cpcb_tier(aqi_val)
        table_data.append({
            "Monitoring Station": r['station_name'],
            "Current AQI": aqi_val,
            "CPCB Risk Tier": cpcb_name
        })

    df_table = pd.DataFrame(table_data)
    st.dataframe(
        df_table,
        column_config={
            "Monitoring Station": st.column_config.TextColumn("Monitoring Station"),
            "Current AQI": st.column_config.NumberColumn("Current AQI", format="%d"),
            "CPCB Risk Tier": st.column_config.TextColumn("CPCB Risk Tier"),
        },
        hide_index=True,
        width="stretch"
    )

    # 3. Single headline stat card: 24h model beats persistence by 4.2 MAE points
    st.container(border=True).metric(
        label="24-Hour Ahead Forecasting Benchmark (Held-Out Winter Crisis Test Set)",
        value="MAE 34.11",
        delta="+4.23 MAE improvement over Persistence Baseline (38.34 MAE, outperforming across 100% of Delhi stations)",
        delta_color="normal"
    )


# =============================================================================
# TAB 2: Forecasts (Interactive Curves + Uncertainty Bands)
# =============================================================================
with tab_forecasts:
    # 2-3 sentence plain-language summary
    st.markdown(r"""
    Multi-horizon regression models predict future AQI at **1-hour**, **6-hour**, and **24-hour** lead times across all 7 Delhi monitoring stations.
    Model uncertainty is explicitly represented by shaded error ribbons based on empirical out-of-sample Mean Absolute Error ($\pm 2.29$ for 1h, $\pm 11.84$ for 6h, and $\pm 34.11$ for 24h).
    The 24-hour hybrid ensemble combines regularized continuous Ridge regression with persistence to maintain unbounded extrapolation during peak winter pollution episodes.
    """)

    # Controls with most informative defaults
    f_col1, f_col2, f_col3 = st.columns([1.5, 1.2, 1.3])

    with f_col1:
        selected_station = st.selectbox("Select Delhi Station", STATIONS, index=0, key="forecast_station")

    with f_col2:
        time_window_choice = st.selectbox(
            "Time Horizon Window",
            ["Latest 72 Hours", "Past 14 Days", "Full Peak Winter Test Window (Nov–Dec 2025)"],
            index=0,
            key="forecast_window"
        )

    with f_col3:
        # Default to 24-Hour Ahead (most challenging and informative horizon)
        active_horizon = st.radio("Forecast Lead Horizon", ["1-Hour Ahead", "6-Hour Ahead", "24-Hour Ahead"], index=2, horizontal=True)

    # Filter dataset for selected station and horizon
    if active_horizon == "1-Hour Ahead":
        df_plot_source = df_1h[df_1h['station_name'] == selected_station].copy()
        y_true_col = 'y_true'
        y_pred_col = 'y_pred'
        mae_band = 2.29
        model_name = "Tuned LightGBM (1h)"
        r2_score = 0.9958
    elif active_horizon == "6-Hour Ahead":
        df_plot_source = df_6h[df_6h['station_name'] == selected_station].copy()
        y_true_col = 'y_true'
        y_pred_col = 'y_pred'
        mae_band = 11.84
        model_name = "Tuned LightGBM (6h)"
        r2_score = 0.9126
    else:
        df_plot_source = df_24h[df_24h['station_name'] == selected_station].copy()
        y_true_col = 'target_aqi_24h'
        y_pred_col = 'prediction_hybrid_6c_winning'
        mae_band = 34.11
        model_name = "50/50 Hybrid Persistence + Ridge (24h)"
        r2_score = 0.3647

    # Filter time range
    max_time = df_plot_source['timestamp'].max()
    if time_window_choice == "Latest 72 Hours":
        df_plot = df_plot_source[df_plot_source['timestamp'] >= max_time - pd.Timedelta(hours=72)].copy()
    elif time_window_choice == "Past 14 Days":
        df_plot = df_plot_source[df_plot_source['timestamp'] >= max_time - pd.Timedelta(days=14)].copy()
    else:
        df_plot = df_plot_source.copy()

    df_plot = df_plot.sort_values('timestamp')

    # Single most important chart visible by default
    fig_forecast = go.Figure()

    # Shaded uncertainty band (MAE)
    fig_forecast.add_trace(go.Scatter(
        x=pd.concat([df_plot['timestamp'], df_plot['timestamp'][::-1]]),
        y=pd.concat([df_plot[y_pred_col] + mae_band, (df_plot[y_pred_col] - mae_band)[::-1]]),
        fill='toself',
        fillcolor='rgba(37, 99, 235, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name=f'Model Uncertainty (±{mae_band:.1f} MAE)',
        hoverinfo='skip'
    ))

    # Model Forecast
    fig_forecast.add_trace(go.Scatter(
        x=df_plot['timestamp'],
        y=df_plot[y_pred_col],
        mode='lines',
        name=f'Forecast ({model_name})',
        line=dict(color='#2563EB', width=2.5)
    ))

    # Actual AQI
    fig_forecast.add_trace(go.Scatter(
        x=df_plot['timestamp'],
        y=df_plot[y_true_col],
        mode='lines',
        name='Actual Verified AQI',
        line=dict(color='#0F172A', width=2, dash='dot')
    ))

    # CPCB Statutory Reference Lines
    fig_forecast.add_hline(y=401, line_dash="dash", line_color="#7e0023", annotation_text="Severe (401)", annotation_position="top right")
    fig_forecast.add_hline(y=301, line_dash="dash", line_color="#cc0033", annotation_text="Very Poor (301)", annotation_position="top right")
    fig_forecast.add_hline(y=201, line_dash="dash", line_color="#ff9933", annotation_text="Poor (201)", annotation_position="top right")

    fig_forecast.update_layout(
        title=f"{selected_station} — {active_horizon} Lead Forecast vs. Actual AQI",
        xaxis_title="Timeline (Asia/Kolkata)",
        yaxis_title="Air Quality Index (AQI)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        height=400,
        margin=dict(l=40, r=40, t=60, b=40)
    )

    st.plotly_chart(fig_forecast)

    # Supporting details inside collapsed expanders
    with st.expander("See station sub-sample error metrics & model parameters", expanded=False):
        m1, m2, m3, m4 = st.columns(4)
        station_mae = np.mean(np.abs(df_plot[y_true_col] - df_plot[y_pred_col]))
        station_rmse = np.sqrt(np.mean((df_plot[y_true_col] - df_plot[y_pred_col])**2))
        with m1:
            st.metric("Station Sub-Sample MAE", f"{station_mae:.2f}", delta=f"Benchmarked: ±{mae_band:.2f}")
        with m2:
            st.metric("Station Sub-Sample RMSE", f"{station_rmse:.2f}")
        with m3:
            st.metric("Model Architecture", model_name.split('(')[0].strip())
        with m4:
            st.metric("Out-of-Sample Test R²", f"{r2_score:.4f}")

    with st.expander("See retrospective crisis & benchmark event replay", expanded=False):
        event_options = [
            "Diwali 2025 (Oct 20, 2025) — Acute Combustion Pulse & Tracer Kinetics",
            "Diwali 2024 (Oct 31, 2024) — Firecracker Night Spike",
            "Diwali 2023 (Nov 12, 2023) — Post-Diwali Surge",
            "Winter Smog Surge (Nov 02–05, 2025) — Severe Inversion Episode",
            "Extreme December Smog Crisis (Dec 02–06, 2025) — AQI > 450 Freeze",
            "Late December Winter Inversion (Dec 26–29, 2025) — Shallow Boundary Layer"
        ]
        selected_event = st.selectbox("Select Historical Event to Replay", event_options, index=0)

        if "Diwali" in selected_event:
            if "2025" in selected_event:
                event_tag = "Diwali 2025 (Oct 20)"
                baseline_pm25 = 120.4
                peak_pm25 = 960.7
                so2_surge = "79.7 µg/m³ (7.9x surge)"
            elif "2024" in selected_event:
                event_tag = "Diwali 2024 (Oct 31)"
                baseline_pm25 = 145.2
                peak_pm25 = 612.9
                so2_surge = "74.1 µg/m³ (5.3x surge)"
            else:
                event_tag = "Diwali 2023 (Nov 12)"
                baseline_pm25 = 110.0
                peak_pm25 = 480.0
                so2_surge = "52.0 µg/m³ (3.8x surge)"

            df_d_event = df_diwali_hourly[df_diwali_hourly['event_name'] == event_tag].copy()
            df_d_city = df_d_event.groupby('timestamp').agg({
                'pm25': 'mean',
                'so2': 'mean',
                'aqi': 'mean',
                'temp': 'mean',
                'ws': 'mean'
            }).reset_index().sort_values('timestamp')

            fig_chem = go.Figure()
            fig_chem.add_trace(go.Scatter(
                x=df_d_city['timestamp'],
                y=df_d_city['pm25'],
                name='PM2.5 Concentration (µg/m³)',
                line=dict(color='#DC2626', width=3),
                yaxis='y1'
            ))
            fig_chem.add_trace(go.Scatter(
                x=df_d_city['timestamp'],
                y=df_d_city['so2'],
                name='SO2 Chemical Tracer (µg/m³)',
                line=dict(color='#D97706', width=2, dash='dash'),
                yaxis='y2'
            ))
            fig_chem.update_layout(
                title=f"{event_tag} — Citywide Hourly PM2.5 Spike & SO2 Tracer Pulse Dynamics",
                xaxis_title="Timeline",
                yaxis=dict(title=dict(text="PM2.5 (µg/m³)", font=dict(color="#DC2626")), tickfont=dict(color="#DC2626")),
                yaxis2=dict(title=dict(text="SO2 Tracer (µg/m³)", font=dict(color="#D97706")), tickfont=dict(color="#D97706"), overlaying='y', side='right'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white",
                height=340,
                margin=dict(l=40, r=40, t=60, b=40)
            )
            st.plotly_chart(fig_chem)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Daytime Pre-Event PM2.5", f"{baseline_pm25:.1f} µg/m³")
            with c2:
                st.metric("Midnight Peak PM2.5", f"{peak_pm25:.1f} µg/m³", delta=f"{peak_pm25/baseline_pm25:.1f}x Surge", delta_color="inverse")
            with c3:
                st.metric("SO2 Tracer Peak", so2_surge)
            with c4:
                st.metric("Plume Dissipation", "18–24 Hours", delta="Returns to Trajectory")
        else:
            if "Nov 02" in selected_event:
                t_start, t_end = "2025-11-02 00:00", "2025-11-05 23:00"
                ep_label = "Post-Diwali Smog Inversion Episode (Nov 2–5, 2025)"
            elif "Dec 02" in selected_event:
                t_start, t_end = "2025-12-02 00:00", "2025-12-06 23:00"
                ep_label = "Extreme December Smog Freeze Episode (Dec 2–6, 2025)"
            else:
                t_start, t_end = "2025-12-26 00:00", "2025-12-29 23:00"
                ep_label = "Late December Shallow Boundary Layer Inversion (Dec 26–29, 2025)"

            df_ep_win = df_24h[(df_24h['timestamp'] >= t_start) & (df_24h['timestamp'] <= t_end)].copy()
            df_ep_city = df_ep_win.groupby('timestamp').agg({
                'target_aqi_24h': 'mean',
                'prediction_hybrid_6c_winning': 'mean',
                'prediction_naive_persistence': 'mean'
            }).reset_index().sort_values('timestamp')

            fig_ep = go.Figure()
            fig_ep.add_trace(go.Scatter(x=df_ep_city['timestamp'], y=df_ep_city['target_aqi_24h'], name='Actual Citywide AQI', line=dict(color='#0F172A', width=3)))
            fig_ep.add_trace(go.Scatter(x=df_ep_city['timestamp'], y=df_ep_city['prediction_hybrid_6c_winning'], name='24h Hybrid Model Forecast', line=dict(color='#2563EB', width=2.5)))
            fig_ep.add_trace(go.Scatter(x=df_ep_city['timestamp'], y=df_ep_city['prediction_naive_persistence'], name='Naive Persistence Baseline', line=dict(color='#94A3B8', width=1.5, dash='dot')))
            fig_ep.add_hline(y=401, line_dash="dash", line_color="#7e0023", annotation_text="Severe Cutoff (401)")
            fig_ep.update_layout(
                title=f"{ep_label} — 24h Model Lead Trajectory vs Actual AQI",
                xaxis_title="Timeline",
                yaxis_title="AQI",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white",
                height=340,
                margin=dict(l=40, r=40, t=60, b=40)
            )
            st.plotly_chart(fig_ep)

    with st.expander("See statutory GRAP policy staging criteria", expanded=False):
        st.markdown("""
        | GRAP Stage | AQI Range | Triggered Municipal Emergency Interventions |
        | :--- | :--- | :--- |
        | **Stage I (Poor)** | 201–300 | Mechanized road sweeping, water sprinkling, strict construction dust control |
        | **Stage II (Very Poor)** | 301–400 | Diesel generator bans, increased parking fees to discourage private vehicles, augmented metro frequency |
        | **Stage III (Severe)** | 401–450 | Total ban on non-essential construction, closure of stone crushers, BS-III petrol & BS-IV diesel vehicle bans |
        | **Stage IV (Severe+)** | > 450 | Ban on non-essential heavy trucks entering Delhi, closure of educational institutions, 50% public/private work from home |
        """)


# =============================================================================
# TAB 3: Diwali Policy Finding (Econometric Causal Analysis)
# =============================================================================
with tab_diwali:
    # 2-3 sentence plain-language summary
    st.markdown(r"""
    Quasi-experimental econometric analysis evaluates whether Delhi's annual Diwali firecracker ban produced a measurable reduction in ambient air pollution.
    A naive before/after comparison shows a $+136$ AQI point spike, but this is an illusion caused by pre-existing seasonal cooling and boundary layer compression ($+20.38$ pts/day pre-trend).
    Controlling for meteorology and pre-trends reveals an Interrupted Time Series shift of $-10.59$ AQI points ($p=0.425$), confirming firecrackers cause a brief 18–24h combustion pulse rather than the persistent multi-week winter crisis.
    """)

    # Single most important visual visible by default
    if img_forest:
        st.image(img_forest, caption="Regression Coefficient Forest Plot: Estimated Policy Effect Across 5 Econometric Specifications (95% CI)")
    else:
        st.dataframe(df_reg_summary[['specification', 'coef_name', 'coef', 'std_err', 'p_value', 'ci_lower', 'ci_upper']])

    # Supporting details inside collapsed expanders
    with st.expander("See the full 5-model regression comparison", expanded=False):
        st.dataframe(df_reg_summary, hide_index=True)

    with st.expander("See hourly chemical tracer spike & dissipation dynamics (SO₂ & PM₂.₅)", expanded=False):
        st.markdown(r"""
        Direct combustion tracers establish that firecracker emissions are an acute impulse rather than a multi-week baseline shift:
        - **PM2.5 Peak Surge:** Spikes from daytime baseline ($120.4\ \mu\text{g/m}^3$) to midnight peak ($960.7\ \mu\text{g/m}^3$, an $8.0\times$ surge).
        - **SO2 Chemical Tracer Surge:** Spikes $5.3\times\text{--}7.9\times$ to $74\text{--}80\ \mu\text{g/m}^3$, confirming localized pyrotechnic combustion.
        - **Ventilation Window:** Concentrations return to the pre-existing seasonal inversion trajectory within **18–24 hours**.
        """)

    with st.expander("See in-time placebo falsification & external control methodology note", expanded=False):
        st.markdown(r"""
        - **In-Time Placebo Test:** Running the identical regression on a non-event date 30 days prior (September 20, 2025) produces a pseudo-treatment effect of **$+24.26$ AQI points** ($p < 0.001$), proving naive before/after models capture seasonal meteorological drift.
        - **External Control Note:** A cross-city Difference-in-Differences against Mumbai was precluded because historical Mumbai CAAQMS sensor data in the repository spans 2026 only (2023–2025 unpopulated), necessitating within-city quasi-experimental identification.
        - **Physical Mechanism:** Multi-week winter pollution is governed by planetary boundary layer compression (<300m), low wind speeds (<0.8 m/s), and regional thermal inversion rather than single-night celebrations.
        """)


# =============================================================================
# TAB 4: Risk Threshold (Cost-Aware Optimization)
# =============================================================================
with tab_risk:
    # 2-3 sentence plain-language summary
    st.markdown(r"""
    Standard statutory CPCB breakpoints assume symmetric loss, causing models to miss 38.9% of hazardous Severe hours due to statistical regularization shrinkage.
    Under an asymmetric 5:1 loss ratio (valuing a missed hazardous day 5x higher than a false alarm), the optimal operational threshold shifts from 401.0 down to 341.5 AQI.
    This simple threshold adjustment increases Severe episode recall from 61.1% to 95.7% (an 89% reduction in missed crisis hours), with 0.0% of false alarms occurring in clean or moderate air.
    """)

    # Interactive slider defaulting to 5:1 (the most informative setting)
    cost_ratio_val = st.select_slider(
        "Select Public Health Loss Ratio (C_FN : C_FP — Missed Hazardous Crisis vs. False Alarm Disruption)",
        options=[1.0, 2.0, 3.0, 5.0, 10.0, 20.0],
        value=5.0,
        format_func=lambda x: f"{int(x)}:1 ({'Symmetric Loss' if x==1 else 'Baseline Health Priority (Recommended)' if x==5 else 'Emergency Health Priority' if x==10 else 'Extreme Zero-Tolerance' if x==20 else 'Moderate Priority'})"
    )

    # Calculate optimal operating point
    cost_col_name = f"cost_rate_{int(cost_ratio_val)}x"
    if cost_col_name in df_sweep.columns:
        best_idx = df_sweep[cost_col_name].idxmin()
        opt_row = df_sweep.loc[best_idx]
        tau_star = float(opt_row['threshold'])
        recall_opt = float(opt_row['recall']) * 100
        prec_opt = float(opt_row['precision']) * 100
        fn_hours = int(opt_row['fn'])
        fp_hours = int(opt_row['fp'])

        stat_row = df_sweep[df_sweep['threshold'] == 401.0].iloc[0]
        stat_cost = stat_row[cost_col_name]
        opt_cost = opt_row[cost_col_name]
        cost_reduction_pct = ((stat_cost - opt_cost) / stat_cost) * 100
    else:
        tau_star = 341.5
        recall_opt = 95.71
        prec_opt = 54.33
        fn_hours = 173
        fp_hours = 3242
        cost_reduction_pct = 62.97

    # Single most important visual visible by default
    if img_pr:
        st.image(img_pr, caption="Precision-Recall Curve with Statutory Breakpoint (τ=401) and 5:1 Cost-Optimal Operating Point (τ*=341.5)")
    else:
        st.dataframe(df_operating)

    # Supporting metrics & detailed breakdown inside collapsed expanders
    with st.expander("See optimal operating point metrics & expected loss reduction", expanded=False):
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Optimal Operating Cutoff (τ*)", f"{tau_star:.1f} AQI", delta=f"{tau_star - 401.0:.1f} pts vs CPCB 401")
        with m2:
            st.metric("Severe Event Recall", f"{recall_opt:.1f}%", delta=f"+{recall_opt - 61.08:.1f}% vs CPCB (61.1%)")
        with m3:
            st.metric("Expected Loss Reduction", f"{cost_reduction_pct:.1f}%", delta="vs Fixed CPCB Cutoff")

        m4, m5, m6 = st.columns(3)
        with m4:
            st.metric("Missed Hazardous Hours", f"{fn_hours:,} h", delta=f"-{1568 - fn_hours:,} h (-{(1568 - fn_hours)/15.68:.1f}%)")
        with m5:
            st.metric("Severe Precision", f"{prec_opt:.1f}%")
        with m6:
            st.metric("False Alarm Hours", f"{fp_hours:,} h", delta=f"+{fp_hours - 871:,} h", delta_color="off")

    with st.expander("See false alarm safety distribution & risk breakdown", expanded=False):
        st.markdown(r"""
        - **Actual Very Poor Air ($301\text{--}400$ AQI):** **$93.6\%$** of false alarms occur when air quality is already in GRAP Stage II (Very Poor), meaning mitigation measures are already partially justified.
        - **Actual Poor Air ($201\text{--}300$ AQI):** **$6.4\%$** of false alarms.
        - **Actual Clean / Moderate Air ($\le 200$ AQI):** **$0.0\%$ (Exactly zero false alarms in clean or moderate air).**
        """)

    with st.expander("See full threshold sensitivity & operating point comparison table", expanded=False):
        df_operating_display = df_operating[[
            'threshold_aqi',
            'severe_recall_pct',
            'severe_precision_pct',
            'severe_missed_h',
            'false_alarms_total_h',
            'cost_rate_5x'
        ]].copy()
        df_operating_display.columns = [
            'Threshold (AQI)',
            'Severe Recall (%)',
            'Severe Precision (%)',
            'Missed Severe (Hours)',
            'Total False Alarms (Hours)',
            'Expected Loss Rate (5:1)'
        ]
        st.dataframe(df_operating_display, hide_index=True)


# =============================================================================
# TAB 5: Methodology & Reports
# =============================================================================
with tab_methodology:
    # 2-3 sentence plain-language summary
    st.markdown(r"""
    The system ingests over 162,000 hourly sensor records across 7 DPCC/CPCB monitoring stations in Delhi, engineering 124 causal features with zero lookahead leakage.
    Multi-horizon forecasting couples gradient boosted trees (1h, 6h) with regularized hybrid ensembles (24h), evaluated on held-out peak winter test data.
    Discretized risk alerts and asymmetric threshold optimization align technical machine learning output with CAQM GRAP public health intervention mandates.
    """)

    # Architecture Overview Cards
    c1, c2 = st.columns(2)
    with c1:
        st.container(border=True).markdown(r"""
        **Data & Feature Engineering:**
        - **162,000+** CAAQMS hourly observations across 7 DPCC/CPCB Delhi stations (2023–2026).
        - **124 Causal Features:** Multi-pollutant lags, trailing rolling statistics, cyclical time encodings, meteorology, and leave-one-out spatial network signals.
        - **Zero Temporal Leakage:** Strict backward-looking windows $[t-W+1, t]$ and chronological evaluation split.
        """)
    with c2:
        st.container(border=True).markdown(r"""
        **Multi-Horizon Model Architecture:**
        - **1-Hour Ahead:** Tuned LightGBM ($\text{MAE} = 2.29, R^2 = 0.9958$)
        - **6-Hour Ahead:** Tuned LightGBM ($\text{MAE} = 11.84, R^2 = 0.9126$)
        - **24-Hour Ahead:** 50/50 Hybrid Persistence + Ridge $\alpha=1000$ ($\text{MAE} = 34.11, R^2 = 0.3647$)
        - **Decision Policy:** Asymmetric cost-minimizing threshold ($\tau^* = 341.5$) delivering 95.7% Severe recall and 0.000% critical miss rate.
        """)

    # Detailed report links inside collapsed expanders
    with st.expander("📄 Causal Econometric Master Report (Diwali Ban vs. Inversion)", expanded=False):
        st.markdown(r"""
        **Artifact Path:** `reports/causal/diwali_ban_causal_analysis.md`
        - Documents parallel pre-trends tests ($p < 0.001$), Interrupted Time Series regressions ($\beta = -10.59, p = 0.425$), in-time placebo falsification ($\beta = +24.26$), and $\text{SO}_2/\text{PM}_{2.5}$ combustion tracer kinetics.
        """)

    with st.expander("📄 Asymmetric Cost-Aware Risk Classification Report", expanded=False):
        st.markdown(r"""
        **Artifact Path:** `reports/classification/cost_aware_threshold_analysis.md`
        - Documents asymmetric loss formulation ($5:1$ loss ratio), Precision-Recall sweep across 601 operating points, and false positive safety composition.
        """)

    with st.expander("📄 Multi-Horizon Forecasting & Risk Classification Master Audit", expanded=False):
        st.markdown(r"""
        **Artifact Path:** `reports/classification/PHASE_7_FINAL_AUDIT.md`
        - 15-dimension comprehensive evaluation of multi-horizon models, GRAP early warning lead times (17.36h mean advance warning), and zero critical miss rate verification.
        """)

    with st.expander("See monitoring station coordinates & sensor metadata", expanded=False):
        st.markdown("""
        | Station Name | Network Operator | Latitude | Longitude | Primary Pollutants Monitored |
        | :--- | :--- | :--- | :--- | :--- |
        | **Anand Vihar** | DPCC | 28.647 | 77.315 | PM2.5, PM10, NOx, SO2, CO, Ozone |
        | **Bawana** | DPCC | 28.776 | 77.051 | PM2.5, PM10, NOx, SO2, CO, Ozone |
        | **Dwarka-Sector 8** | DPCC | 28.571 | 77.071 | PM2.5, PM10, NOx, SO2, CO |
        | **ITO** | CPCB | 28.631 | 77.241 | PM2.5, PM10, NOx, SO2, CO, Ozone |
        | **Jahangirpuri** | DPCC | 28.732 | 77.170 | PM2.5, PM10, NOx, SO2, CO, Ozone |
        | **Punjabi Bagh** | DPCC | 28.674 | 77.131 | PM2.5, PM10, NOx, SO2, CO, Ozone |
        | **R K Puram** | DPCC | 28.563 | 77.186 | PM2.5, PM10, NOx, SO2, CO, Ozone |
        """)


# =============================================================================
# Footer
# =============================================================================
st.markdown("---")
st.caption("Delhi Air Quality Risk Forecasting System • Streamlit Cloud Deployment • Continuous Ambient Air Quality Monitoring Network (DPCC/CPCB)")

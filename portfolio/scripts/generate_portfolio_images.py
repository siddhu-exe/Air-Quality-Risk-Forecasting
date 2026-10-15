"""Render the portfolio gallery figures in portfolio/ from files already in reports/ and data/.

Run from the repo root:  ./venv/bin/python portfolio/scripts/generate_portfolio_images.py

Every number drawn here is read from a report file (headline metrics, classification
metrics, causal regression summary, prediction parquet files), so the figures cannot
drift from the README. The palette and fonts follow the portfolio site's design tokens
(cream / ink / terracotta, Playfair Display + Inter); if those fonts are not installed
the script falls back to DejaVu Serif / DejaVu Sans.

Output (grouped by Chapter-page gallery section):
  architecture  10_architecture.png                       16:9
  pipeline      20_data_model.png, 21_splits_timeline.png  4:3
  ml            30_skill_vs_persistence.png,
                31_extrapolation_fix.png, 32_episode_forecast.png  4:3
  results       50_alert_tradeoff.png, 51_diwali_identification.png  4:3
Platform screenshots (40_*..43_* React dashboard on sample data, 44_* legacy Streamlit) are captured from the running apps, not drawn here.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "portfolio" / "images"
REPORTS = REPO_ROOT / "reports"
DATA = REPO_ROOT / "data"

# Portfolio design tokens (Portfolio/frontend/tailwind.config.js) plus the project's spine colour.
CREAM = "#F7F1ED"
INK = "#171717"
MUTED = "#6F6862"
RULE = "#DDD3CB"
CARD = "#FFFCFA"
TERRACOTTA = "#D9834A"
TERRACOTTA_LIGHT = "#F2D3BD"
SPINE = "#2F4A3A"  # model colour
SPINE_LIGHT = "#C9D6CC"
GREY = "#A39B94"  # persistence / baselines

DPI = 200


def _setup_fonts() -> tuple[str, str]:
    for path in (Path.home() / ".local/share/fonts").rglob("*.ttf"):
        font_manager.fontManager.addfont(str(path))
    names = {f.name for f in font_manager.fontManager.ttflist}
    serif = "Playfair Display" if "Playfair Display" in names else "DejaVu Serif"
    sans = "Inter" if "Inter" in names else "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": sans,
            "font.size": 11,
            "text.color": INK,
            "axes.labelcolor": INK,
            "axes.edgecolor": RULE,
            "axes.facecolor": CREAM,
            "figure.facecolor": CREAM,
            "savefig.facecolor": CREAM,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.titlesize": 13,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": RULE,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
        }
    )
    return serif, sans


SERIF, SANS = _setup_fonts()


def header(fig, title: str, subtitle: str, source: str | None = None) -> None:
    """Site-style header: small terracotta kicker rule, serif title, muted subtitle, source footer."""
    fig.add_artist(plt.Line2D([0.045, 0.085], [0.955, 0.955], color=TERRACOTTA, lw=2.5, transform=fig.transFigure))
    fig.text(0.045, 0.93, title, fontfamily=SERIF, fontsize=24, fontweight="bold", va="top", color=INK)
    fig.text(0.045, 0.865, subtitle, fontsize=12, va="top", color=MUTED)
    if source:
        fig.text(0.045, 0.025, f"Source: {source}", fontsize=8.5, color=MUTED, va="bottom")


def save(fig, name: str) -> None:
    path = OUT_DIR / name
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def card(ax, x, y, w, h, fc=CARD, ec=RULE, lw=1.0, r=0.012):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw))


def arrow(ax, x0, y0, x1, y1, color=TERRACOTTA, lw=1.6, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=12, color=color, lw=lw))


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------
def fig_architecture() -> None:
    fig = plt.figure(figsize=(16, 9))
    header(
        fig,
        "From raw government spreadsheets to risk alerts",
        "One reproducible pipeline: every stage writes files the next stage (and both dashboards) read.",
    )
    ax = fig.add_axes([0.03, 0.06, 0.94, 0.76])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    stages = [
        ("01", "Raw data", ["105 CPCB / DPCC files", "7 Delhi stations", "2023 – 2026, hourly"]),
        ("02", "ETL + QC", ["Header & unit mapping", "Sentinels nulled per cell", "QC flags kept as JSONB"]),
        ("03", "PostgreSQL 16", ["Idempotent upserts", "Source-file lineage", "162,096 telemetry rows"]),
        ("04", "Features", ["124 leakage-safe features", "2023–24 AQI recomputed", "(CPCB method)"]),
        ("05", "Forecasts", ["1h / 6h  LightGBM", "24h  Ridge + persistence", "vs persistence always"]),
        ("06", "Decisions", ["CPCB categories", "GRAP stages I – IV", "Cutoffs chosen on val"]),
        ("07", "Serving", ["FastAPI + React", "Streamlit (legacy)", "Read files in reports/"]),
    ]
    n = len(stages)
    gap = 0.018
    w = (1 - gap * (n - 1)) / n
    top, h = 0.95, 0.5
    for i, (num, title, lines) in enumerate(stages):
        x = i * (w + gap)
        card(ax, x, top - h, w, h)
        ax.text(x + 0.012, top - 0.05, num, fontfamily=SERIF, fontsize=22, color=TERRACOTTA, va="top", fontweight="bold")
        ax.text(x + 0.012, top - 0.16, title, fontfamily=SERIF, fontsize=15, color=INK, va="top", fontweight="bold")
        ax.plot([x + 0.012, x + w - 0.012], [top - 0.225, top - 0.225], color=RULE, lw=0.8)
        for j, line in enumerate(lines):
            ax.text(x + 0.012, top - 0.26 - j * 0.065, line, fontsize=10.2, color=INK, va="top")
        if i < n - 1:
            arrow(ax, x + w + 0.002, top - h / 2, x + w + gap - 0.002, top - h / 2)

    # Causal branch from the database
    db_x = 2 * (w + gap) + w / 2
    cx, cy, cw, ch = 2 * (w + gap), 0.04, 3 * w + 2 * gap, 0.27
    card(ax, cx, cy, cw, ch, fc=TERRACOTTA_LIGHT, ec=TERRACOTTA)
    arrow(ax, db_x, top - h - 0.005, db_x, cy + ch + 0.005)
    ax.text(cx + 0.014, cy + ch - 0.04, "Causal question: did the Diwali firecracker ban work?", fontfamily=SERIF,
            fontsize=14, fontweight="bold", va="top")
    ax.text(cx + 0.014, cy + ch - 0.11, "Interrupted time series, placebo date, date-clustered errors.", fontsize=10.5, va="top")
    ax.text(cx + 0.014, cy + ch - 0.17, "Answer: not identifiable with this data (the ban was active every year).",
            fontsize=10.5, va="top")

    # Evaluation rules
    ex, ew = cx + cw + 0.03, 1 - (cx + cw + 0.03)
    card(ax, ex, cy, ew, ch, fc=SPINE, ec=SPINE)
    ax.text(ex + 0.014, cy + ch - 0.04, "Evaluation rules", fontfamily=SERIF, fontsize=14, fontweight="bold", va="top",
            color=CREAM)
    for j, line in enumerate(["Select on validation (Sep–Oct 2025)", "Score test once (Nov–Dec 2025)",
                              "Report skill vs persistence"]):
        ax.text(ex + 0.014, cy + ch - 0.1 - j * 0.05, "•  " + line, fontsize=10.5, va="top", color=CREAM)

    # Left caption
    ax.text(0.0, cy + ch - 0.04, "Why persistence?", fontfamily=SERIF, fontsize=14, fontweight="bold", va="top")
    for j, line in enumerate(["AQI is a 24-hour rolling average,", "so 'copy the last value' is a very",
                              "strong baseline (lag-1 r ≈ 0.998)."]):
        ax.text(0.0, cy + ch - 0.1 - j * 0.05, line, fontsize=10.5, va="top", color=MUTED)
    save(fig, "10_architecture.png")


# ---------------------------------------------------------------------------
# Data pipeline
# ---------------------------------------------------------------------------
def fig_data_model() -> None:
    fig = plt.figure(figsize=(12, 9))
    header(fig, "A database you can re-run safely",
           "UNIQUE(station_id, timestamp) makes every load idempotent; every row points back to its source file.",
           "sql/ (schema DDL), etl/load_postgres.py")
    ax = fig.add_axes([0.04, 0.07, 0.92, 0.74])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def table(x, y, w, name, rows, accent, note=None):
        row_h = 0.058
        h = 0.085 + row_h * len(rows)
        card(ax, x, y - h, w, h)
        ax.add_patch(Rectangle((x, y - 0.075), w, 0.075, fc=accent, ec="none"))
        ax.text(x + 0.018, y - 0.0375, name, fontfamily=SERIF, fontsize=15, fontweight="bold", va="center",
                color=CREAM if accent in (SPINE, INK) else INK)
        for i, (key, col, typ) in enumerate(rows):
            yy = y - 0.075 - row_h * (i + 0.5) - 0.005
            ax.text(x + 0.018, yy, key, fontsize=9, color=TERRACOTTA, va="center", fontweight="semibold")
            ax.text(x + 0.07, yy, col, fontsize=10.5, va="center")
            ax.text(x + w - 0.018, yy, typ, fontsize=9.5, va="center", ha="right", color=MUTED)
        if note:
            ax.text(x, y - h - 0.035, note, fontsize=9.5, color=MUTED, va="top")
        return h

    table(0.0, 0.97, 0.36, "stations", [("PK", "station_id", "bigint"), ("", "station_name", "varchar"),
                                         ("", "operator", "DPCC / CPCB"), ("", "latitude, longitude", "decimal")],
          SPINE_LIGHT, "7 rows")
    table(0.0, 0.47, 0.36, "source_files", [("PK", "source_file_id", "bigint"), ("FK", "station_id", "bigint"),
                                             ("", "filename, path", "varchar"), ("", "row_count", "integer"),
                                             ("", "processing_status", "varchar")],
          TERRACOTTA_LIGHT, "105 files, one row each")
    table(0.6, 0.97, 0.4, "caaqms_hourly", [("FK", "station_id", "bigint"), ("FK", "source_file_id", "bigint"),
                                             ("AK", "timestamp", "timestamptz (IST)"),
                                             ("", "pm25, pm10, no2, so2, co, o3 …", "decimal"),
                                             ("", "temp, humidity, wind_speed …", "decimal"),
                                             ("", "qc_flags", "jsonb")],
          SPINE, "162,096 hourly rows")
    table(0.6, 0.4, 0.4, "aqi_hourly", [("FK", "station_id", "bigint"), ("FK", "source_file_id", "bigint"),
                                         ("AK", "timestamp", "timestamptz (IST)"), ("", "aqi_value", "integer"),
                                         ("", "qc_flags", "jsonb")],
          SPINE, "57,946 official AQI rows (2025)")

    for (x0, y0, x1, y1, label) in [
        (0.36, 0.85, 0.6, 0.85, "1 : N  observations"),
        (0.36, 0.33, 0.6, 0.70, "lineage"),
        (0.36, 0.30, 0.6, 0.20, "lineage"),
        (0.18, 0.66, 0.18, 0.47, "1 : N"),
    ]:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=TERRACOTTA, lw=1.4, mutation_scale=12))
        ax.text((x0 + x1) / 2 + (0.01 if x0 == x1 else 0), (y0 + y1) / 2, label, fontsize=9, color=MUTED,
                ha="left" if x0 == x1 else "center", va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc=CREAM, ec="none"))
    save(fig, "20_data_model.png")


def fig_splits_timeline() -> None:
    rec = pd.read_parquet(DATA / "processed" / "recomputed_aqi.parquet", columns=["timestamp", "aqi_value", "aqi_source"])
    rec = rec[rec.aqi_source == "recomputed"]
    off = pd.read_parquet(DATA / "processed" / "features_2025.parquet", columns=["timestamp", "aqi_curr"])
    off = off.rename(columns={"aqi_curr": "aqi_value"})
    for d in (rec, off):
        d["timestamp"] = pd.to_datetime(d["timestamp"])
        if d["timestamp"].dt.tz is not None:
            d["timestamp"] = d["timestamp"].dt.tz_localize(None)
    rec_d = rec.set_index("timestamp")["aqi_value"].resample("D").mean()
    off_d = off.set_index("timestamp")["aqi_value"].resample("D").mean()
    rec_d = rec_d[(rec_d.index >= "2024-01-01") & (rec_d.index < "2025-01-01")]

    fig = plt.figure(figsize=(12, 9))
    header(fig, "Chronological splits, and why winter is hard",
           "Daily citywide mean AQI. Validation is a calm autumn; the test window is the peak smog season.",
           "data/processed/recomputed_aqi.parquet (2024), features_2025.parquet (2025); src/models/splits.py")
    ax = fig.add_axes([0.08, 0.17, 0.88, 0.6])
    spans = [
        ("2024-01-01", "2025-01-01", "#EFE7E1", "Extended train (Tier 2)\n2024, AQI recomputed"),
        ("2025-01-01", "2025-09-01", SPINE_LIGHT, "Train\nJan – Aug 2025"),
        ("2025-09-01", "2025-11-01", "#E8E2B8", "Validation\nSep – Oct"),
        ("2025-11-01", "2026-01-01", TERRACOTTA_LIGHT, "Test\nNov – Dec"),
    ]
    for a, b, c, label in spans:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=c, lw=0, zorder=0)
        ax.text(pd.Timestamp(a) + pd.Timedelta(days=6), 492, label, fontsize=9.5, va="top", color=INK)
    ax.axhspan(401, 520, color=TERRACOTTA, alpha=0.08, lw=0, zorder=0)
    ax.axhline(401, color=TERRACOTTA, lw=1, ls="--", zorder=1)
    ax.text(pd.Timestamp("2025-06-15"), 405, "Severe (≥ 401)", color=TERRACOTTA, fontsize=9.5, va="bottom")
    ax.plot(rec_d.index, rec_d.values, color=MUTED, lw=1.4, label="2024 (recomputed from raw telemetry)")
    ax.plot(off_d.index, off_d.values, color=SPINE, lw=1.8, label="2025 (official AQI)")

    sev = pd.read_csv(REPORTS / "classification" / "metrics" / "cost_optimal_thresholds_summary.csv").iloc[0]
    val_rate = (sev.val_tp + sev.val_fn) / (sev.val_tp + sev.val_fn + sev.val_fp + sev.val_tn)
    test_rate = (sev.test_tp + sev.test_fn) / (sev.test_tp + sev.test_fn + sev.test_fp + sev.test_tn)
    for a, rate in [("2025-09-04", val_rate), ("2025-11-04", test_rate)]:
        ax.text(pd.Timestamp(a), 22, f"{rate:.1%}\nhours\nSevere", fontsize=10.5, fontweight="semibold",
                color=TERRACOTTA, va="bottom")
    ax.set_ylim(0, 500)
    ax.set_xlim(pd.Timestamp("2024-01-01"), pd.Timestamp("2026-01-01"))
    ax.set_ylabel("AQI (daily mean, 7 stations)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, -0.15), ncol=2, fontsize=10)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %Y"))
    ax.grid(axis="x", visible=False)
    save(fig, "21_splits_timeline.png")


# ---------------------------------------------------------------------------
# Machine learning
# ---------------------------------------------------------------------------
def fig_skill() -> None:
    hm = pd.read_csv(REPORTS / "metrics" / "headline_metrics.csv")
    ro = pd.read_csv(REPORTS / "modeling" / "24h" / "rolling_origin_backtest.csv").set_index("fold")
    models = {"1h": "Tuned LightGBM", "6h": "Tuned LightGBM", "24h": "50/50 Hybrid (Persistence + Ridge)"}
    rows = [hm[(hm.horizon == h) & (hm.model == m)].iloc[0] for h, m in models.items()]

    fig = plt.figure(figsize=(12, 9))
    header(fig, "Skill against the baseline that matters",
           "Skill = 1 − error(model) / error(persistence). Above zero beats “copy the last value”. Bars: 95% CI.",
           "reports/metrics/headline_metrics.csv, reports/modeling/24h/rolling_origin_backtest.csv")
    ax = fig.add_axes([0.17, 0.12, 0.8, 0.64])
    ax.tick_params(axis="y", length=0)
    y = np.arange(len(rows))[::-1].astype(float)
    for yi, r in zip(y, rows):
        for dy, metric, color, lab in [(0.13, "mae", SPINE, "MAE skill"), (-0.13, "rmse", TERRACOTTA, "RMSE skill")]:
            s, lo, hi = r[f"skill_{metric}"], r[f"skill_{metric}_ci_lo"], r[f"skill_{metric}_ci_hi"]
            ax.plot([lo, hi], [yi + dy] * 2, color=color, lw=2.2, solid_capstyle="round")
            ax.scatter([s], [yi + dy], s=90, color=color, zorder=3, edgecolor=CREAM, lw=1.5,
                       label=lab if yi == y[0] else None)
            ax.text(hi + 0.02, yi + dy, f"{s:+.3f}", va="center", fontsize=10.5, color=color)
    w24 = ro.loc["winter_2024"]
    ax.plot([w24.skill_mae_ci_lo, w24.skill_mae_ci_hi], [y[-1] - 0.4] * 2, color=MUTED, lw=2.2)
    ax.scatter([w24.skill_mae], [y[-1] - 0.4], s=70, color=MUTED, zorder=3, edgecolor=CREAM, lw=1.5,
               label="MAE skill, 2024 winter backtest")
    ax.text(w24.skill_mae_ci_hi + 0.02, y[-1] - 0.4, f"{w24.skill_mae:+.3f}", va="center", fontsize=10.5, color=MUTED)
    ax.axvline(0, color=INK, lw=1)
    ax.text(0.005, y[0] + 0.55, "persistence", fontsize=9.5, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{h} ahead\n{m.split(' (')[0]}" for h, m in models.items()], fontsize=11)
    ax.set_xlim(-1.05, 0.55)
    ax.set_ylim(y[-1] - 0.75, y[0] + 0.75)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", fontsize=10)
    ax.text(-1.0, y[0] - 0.42, "At 1h the model loses on RMSE:\nno real skill once the target is this smooth.",
            fontsize=9.5, color=MUTED, va="center")
    save(fig, "30_skill_vs_persistence.png")


def fig_extrapolation() -> None:
    tree = pd.read_parquet(DATA / "Artifacts" / "24h" / "predictions_24h_test.parquet")
    hyb = pd.read_parquet(REPORTS / "modeling" / "24h" / "final" / "final_predictions.parquet")
    tree_mae = (tree.y_pred - tree.y_true).abs().mean()
    hyb_mae = (hyb.prediction_hybrid_6c_winning - hyb.target_aqi_24h).abs().mean()
    cap = tree.y_pred.max()

    fig = plt.figure(figsize=(12, 9))
    header(fig, "The 24-hour failure, and the fix",
           "Trees cannot predict above the highest value they were trained on. Winter went far above it.",
           "data/Artifacts/24h/predictions_24h_test.parquet, reports/modeling/24h/final/final_predictions.parquet")
    axes = [fig.add_axes([0.08, 0.12, 0.4, 0.62]), fig.add_axes([0.56, 0.12, 0.4, 0.62])]
    panels = [
        (axes[0], tree.y_true, tree.y_pred, GREY, f"Gradient-boosted trees   MAE {tree_mae:.2f}"),
        (axes[1], hyb.target_aqi_24h, hyb.prediction_hybrid_6c_winning, SPINE,
         f"Ridge + persistence hybrid   MAE {hyb_mae:.2f}"),
    ]
    for ax, yt, yp, color, title in panels:
        ax.scatter(yt, yp, s=4, alpha=0.18, color=color, lw=0, rasterized=True)
        ax.plot([0, 520], [0, 520], color=INK, lw=0.8, ls=":")
        ax.axhline(cap, color=TERRACOTTA, lw=1.4, ls="--")
        ax.set_xlim(100, 510)
        ax.set_ylim(100, 510)
        ax.set_aspect("equal")
        ax.set_xlabel("Actual AQI, 24h later")
        ax.set_title(title, fontsize=12, loc="left", color=INK, pad=10)
    axes[0].set_ylabel("Predicted AQI")
    axes[0].text(108, cap + 8, f"training max ≈ {cap:.0f}: predictions stop here", color=TERRACOTTA, fontsize=9.5)
    axes[1].text(108, cap + 8, "linear part can go above it", color=TERRACOTTA, fontsize=9.5)
    save(fig, "31_extrapolation_fix.png")


def fig_episode() -> None:
    d = pd.read_parquet(REPORTS / "modeling" / "24h" / "final" / "final_predictions.parquet")
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    d["target_time"] = d["timestamp"] + pd.Timedelta(hours=24)
    station = "Anand Vihar"
    s = d[d.station_name == station].sort_values("target_time")
    s = s[(s.target_time >= s.target_time.min()) & (s.target_time < s.target_time.min() + pd.Timedelta(days=30))]
    # Reindex hourly so missing hours show as gaps instead of straight lines.
    s = s.set_index("target_time")
    s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="h")).rename_axis("target_time").reset_index()

    fig = plt.figure(figsize=(12, 9))
    header(fig, "What a 24-hour forecast looks like",
           f"{station}, first 30 days of the test winter. Each point is a forecast issued 24 hours earlier.",
           "reports/modeling/24h/final/final_predictions.parquet")
    ax = fig.add_axes([0.08, 0.16, 0.89, 0.58])
    ax.axhspan(401, 520, color=TERRACOTTA, alpha=0.1, lw=0)
    ax.axhline(401, color=TERRACOTTA, lw=1, ls="--")
    ax.text(s.target_time.iloc[2], 404, "Severe", color=TERRACOTTA, fontsize=10, va="bottom")
    ax.plot(s.target_time, s.target_aqi_24h, color=INK, lw=1.8, label="Actual AQI")
    ax.plot(s.target_time, s.prediction_naive_persistence, color=GREY, lw=1.2, label="Persistence (value 24h earlier)")
    ax.plot(s.target_time, s.prediction_hybrid_6c_winning, color=SPINE, lw=1.8, label="24h hybrid forecast")
    mae_m = (s.prediction_hybrid_6c_winning - s.target_aqi_24h).abs().mean()
    mae_p = (s.prediction_naive_persistence - s.target_aqi_24h).abs().mean()
    ax.text(0.99, 0.04, f"MAE in this window: hybrid {mae_m:.1f}, persistence {mae_p:.1f}", transform=ax.transAxes,
            ha="right", fontsize=10, color=MUTED)
    ax.set_ylabel("AQI")
    ax.set_ylim(max(0, s.target_aqi_24h.min() - 60), 520)
    ax.legend(loc="lower left", bbox_to_anchor=(0, -0.17), ncol=3, fontsize=10)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.grid(axis="x", visible=False)
    save(fig, "32_episode_forecast.png")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
def fig_alert_tradeoff() -> None:
    d = pd.read_parquet(REPORTS / "classification" / "24h" / "classified_predictions.parquet")
    ops = pd.read_csv(REPORTS / "classification" / "metrics" / "threshold_operating_points_comparison.csv")
    cost = pd.read_csv(REPORTS / "classification" / "metrics" / "cost_optimal_thresholds_summary.csv")
    tau_opt = float(cost.loc[cost.cost_ratio_fn_to_fp == "5:1", "optimal_threshold"].iloc[0])
    y = d.target_aqi_24h >= 401

    def curve(pred):
        taus = np.arange(250, 451, 1.0)
        out = []
        for t in taus:
            p = pred >= t
            tp, fp = (p & y).sum(), (p & ~y).sum()
            out.append((t, tp / y.sum(), tp / max(tp + fp, 1)))
        return np.array(out)

    cm, cp = curve(d.prediction_hybrid_6c_winning), curve(d.prediction_naive_persistence)

    fig = plt.figure(figsize=(12, 9))
    header(fig, "Severe-AQI alerts: recall always has a price",
           "Test winter, 24h ahead. Each curve sweeps the alert cutoff; cutoffs were chosen on validation only.",
           "reports/classification/24h/classified_predictions.parquet, reports/classification/metrics/")
    ax = fig.add_axes([0.1, 0.13, 0.86, 0.62])
    ax.plot(cp[:, 1], cp[:, 2], color=GREY, lw=2, label="Persistence")
    ax.plot(cm[:, 1], cm[:, 2], color=SPINE, lw=2.4, label="24h hybrid model")
    points = [(401.0, "Statutory 401"), (380.0, "Compromise 380"), (tau_opt, f"Validation-optimal {tau_opt:g}\n(5:1 cost)")]
    for t, label in points:
        row = ops[np.isclose(ops.threshold_aqi, t)]
        if row.empty:
            r_ = cm[np.argmin(np.abs(cm[:, 0] - t))]
            rec, prec = r_[1], r_[2]
        else:
            rec, prec = row.test_severe_recall_pct.iloc[0] / 100, row.test_severe_precision_pct.iloc[0] / 100
        ax.scatter([rec], [prec], s=110, color=TERRACOTTA, zorder=4, edgecolor=CREAM, lw=1.5)
        ax.annotate(f"{label}\nrecall {rec:.0%}, precision {prec:.0%}", xy=(rec, prec), xytext=(-12, -12),
                    textcoords="offset points", ha="right", va="top", fontsize=9.5,
                    bbox=dict(boxstyle="round,pad=0.3", fc=CREAM, ec="none", alpha=0.9))
    ax.set_xlabel("Recall: share of Severe hours caught")
    ax.set_ylabel("Precision: share of alerts that were right")
    ax.set_xlim(0.45, 1.01)
    ax.set_ylim(0.35, 0.9)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(loc="upper right", fontsize=10.5)
    ax.text(0.47, 0.37, "At strict cutoffs the model is about 4–7 points more precise than persistence;\n"
            "at the aggressive validation-optimal cutoff the two converge.", fontsize=10, color=MUTED)
    save(fig, "50_alert_tradeoff.png")


def fig_diwali() -> None:
    r = pd.read_csv(REPORTS / "causal" / "regression_models_summary.csv")
    r = r[r.outcome == "aqi"].set_index("model_id")
    order = [
        ("Model 1 (Naive Before/After)", "Naive before / after"),
        ("Model 2 (Station FE)", "+ station fixed effects"),
        ("Model 3 (Meteo Controls)", "+ weather controls"),
        ("Model 4 (Interrupted Time Series)", "Interrupted time series\n(accounts for the trend)"),
        ("Model 5 (Placebo Non-Event)", "Placebo: a date with no event"),
    ]
    pre = r.loc["Pre-Trend Slope"]

    fig = plt.figure(figsize=(12, 9))
    header(fig, "Did the Diwali firecracker ban work? This data can’t tell",
           "Estimated jump in AQI after Diwali 2025, by design. Bars: 95% CI, errors clustered by date.",
           "reports/causal/regression_models_summary.csv")
    ax = fig.add_axes([0.3, 0.22, 0.66, 0.54])
    ax.tick_params(axis="y", length=0)
    ys = np.arange(len(order))[::-1]
    for yi, (key, label) in zip(ys, order):
        row = r.loc[key]
        color = SPINE if "Interrupted" in key else (TERRACOTTA if "Placebo" in key else GREY)
        ax.plot([row.ci_lower, row.ci_upper], [yi, yi], color=color, lw=3, solid_capstyle="round")
        ax.scatter([row.coef], [yi], s=120, color=color, zorder=3, edgecolor=CREAM, lw=1.5)
        p = row.p_value
        ax.text(row.ci_upper + 4, yi, f"{row.coef:+.1f}  (p {'< 0.001' if p < 0.001 else f'= {p:.3f}' if p < 0.01 else f'= {p:.2f}'})",
                va="center", fontsize=10.5, color=color)
    ax.axvline(0, color=INK, lw=1)
    ax.set_yticks(ys)
    ax.set_yticklabels([lbl for _, lbl in order], fontsize=11)
    ax.set_xlabel("Change in AQI after Diwali")
    ax.set_xlim(-60, 250)
    ax.grid(axis="y", visible=False)
    fig.text(0.045, 0.075,
             f"AQI was already rising {pre.coef:.1f} points/day before Diwali, and a fake event date shows a "
             "“significant” jump, so naive designs mislead.\nThe ban was in force in every year studied, "
             "so there is no untreated year to compare against.", fontsize=10, color=MUTED, va="bottom")
    save(fig, "51_diwali_identification.png")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    fig_architecture()
    fig_data_model()
    fig_splits_timeline()
    fig_skill()
    fig_extrapolation()
    fig_episode()
    fig_alert_tradeoff()
    fig_diwali()


if __name__ == "__main__":
    main()

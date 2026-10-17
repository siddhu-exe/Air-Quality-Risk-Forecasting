"""Render the portfolio figures into portfolio/images/ from files already in reports/, data/ and .github/.

Run from the repo root:  make portfolio      (or ./venv/bin/python scripts/make_portfolio_figures.py)

Every number drawn here is read from a report, CSV or parquet file, so the figures cannot drift
from the README. Palette and fonts follow the dashboard's design tokens
(frontend/src/design/tokens.ts; Geist / Instrument Serif); if those fonts are not installed the
script falls back to DejaVu Sans / DejaVu Serif. All figures are PNG, 1600 px wide, light background.

Output:
  architecture  10_architecture.png
  pipeline      21_splits_timeline.png
  ml            30_skill_vs_persistence.png, 31_extrapolation_fix.png, 32_episode_forecast.png
  live          60_train_serve_skew.png, 61_baselines_by_horizon.png, 62_replay_skill.png
  results       50_alert_tradeoff.png, 51_diwali_identification.png
Dashboard screenshots (dashboard_*_{desktop,mobile}.png) come from scripts/capture_dashboard.mjs
(Playwright), which `make portfolio` runs after this script.
"""

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "portfolio" / "images"
REPORTS = REPO_ROOT / "reports"
DATA = REPO_ROOT / "data"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# Dashboard design tokens (frontend/src/design/tokens.ts).
PAGE = "#F5F6F4"
SURFACE = "#FFFFFF"
INK = "#15171A"
MUTED = "#5E646B"
LINE = "#E3E5E1"
MODEL = "#2B4C7E"  # accent: the model / the live system
MODEL_LIGHT = "#DCE5F1"
BASELINE = "#8A9097"  # persistence and other baselines
HIGHLIGHT = "#E0803E"  # inverse-panel accent: rules, severe, callouts
HIGHLIGHT_LIGHT = "#F7E3D2"
POSITIVE = "#2C5A39"
NEGATIVE = "#8E2C26"

FIG_WIDTH_PX = 1600


def _setup_fonts() -> tuple[str, str]:
    for path in (REPO_ROOT / "scripts" / "fonts").glob("*.ttf"):
        font_manager.fontManager.addfont(str(path))
    names = {f.name for f in font_manager.fontManager.ttflist}
    serif = "Instrument Serif" if "Instrument Serif" in names else "DejaVu Serif"
    sans = "Geist" if "Geist" in names else "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": sans,
            "font.size": 11,
            "text.color": INK,
            "axes.labelcolor": INK,
            "axes.edgecolor": LINE,
            "axes.facecolor": PAGE,
            "figure.facecolor": PAGE,
            "savefig.facecolor": PAGE,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.titlesize": 13,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": LINE,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
        }
    )
    return serif, sans


SERIF, SANS = _setup_fonts()


def header(fig, title: str, subtitle: str, source: str | None = None) -> None:
    """Site-style header: small terracotta kicker rule, serif title, muted subtitle, source footer."""
    fig.add_artist(plt.Line2D([0.045, 0.085], [0.955, 0.955], color=HIGHLIGHT, lw=2.5, transform=fig.transFigure))
    fig.text(0.045, 0.93, title, fontfamily=SERIF, fontsize=28, fontweight="normal", va="top", color=INK)
    fig.text(0.045, 0.865, subtitle, fontsize=12, va="top", color=MUTED)
    if source:
        fig.text(0.045, 0.025, f"Source: {source}", fontsize=8.5, color=MUTED, va="bottom")


def save(fig, name: str) -> None:
    path = OUT_DIR / name
    fig.savefig(path, dpi=FIG_WIDTH_PX / fig.get_figwidth())
    plt.close(fig)
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def card(ax, x, y, w, h, fc=SURFACE, ec=LINE, lw=1.0, r=0.012):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw))


def arrow(ax, x0, y0, x1, y1, color=HIGHLIGHT, lw=1.6, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=12, color=color, lw=lw))


# ---------------------------------------------------------------------------
# Data pipeline
# ---------------------------------------------------------------------------
def fig_splits_timeline() -> None:
    rec = pd.read_parquet(
        DATA / "processed" / "recomputed_aqi.parquet", columns=["timestamp", "aqi_value", "aqi_source"]
    )
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
    header(
        fig,
        "Chronological splits, and why winter is hard",
        "Daily citywide mean AQI. Validation is a calm autumn; the test window is the peak smog season.",
        "data/processed/recomputed_aqi.parquet (2024), features_2025.parquet (2025); src/models/splits.py",
    )
    ax = fig.add_axes([0.08, 0.17, 0.88, 0.6])
    spans = [
        ("2024-01-01", "2025-01-01", "#EFE7E1", "Extended train (Tier 2)\n2024, AQI recomputed"),
        ("2025-01-01", "2025-09-01", MODEL_LIGHT, "Train\nJan – Aug 2025"),
        ("2025-09-01", "2025-11-01", "#E8E2B8", "Validation\nSep – Oct"),
        ("2025-11-01", "2026-01-01", HIGHLIGHT_LIGHT, "Test\nNov – Dec"),
    ]
    for a, b, c, label in spans:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=c, lw=0, zorder=0)
        ax.text(pd.Timestamp(a) + pd.Timedelta(days=6), 492, label, fontsize=9.5, va="top", color=INK)
    ax.axhspan(401, 520, color=HIGHLIGHT, alpha=0.08, lw=0, zorder=0)
    ax.axhline(401, color=HIGHLIGHT, lw=1, ls="--", zorder=1)
    ax.text(pd.Timestamp("2025-06-15"), 405, "Severe (≥ 401)", color=HIGHLIGHT, fontsize=9.5, va="bottom")
    ax.plot(rec_d.index, rec_d.values, color=MUTED, lw=1.4, label="2024 (recomputed from raw telemetry)")
    ax.plot(off_d.index, off_d.values, color=MODEL, lw=1.8, label="2025 (official AQI)")

    sev = pd.read_csv(REPORTS / "classification" / "metrics" / "cost_optimal_thresholds_summary.csv").iloc[0]
    val_rate = (sev.val_tp + sev.val_fn) / (sev.val_tp + sev.val_fn + sev.val_fp + sev.val_tn)
    test_rate = (sev.test_tp + sev.test_fn) / (sev.test_tp + sev.test_fn + sev.test_fp + sev.test_tn)
    for a, rate in [("2025-09-04", val_rate), ("2025-11-04", test_rate)]:
        ax.text(
            pd.Timestamp(a),
            22,
            f"{rate:.1%}\nhours\nSevere",
            fontsize=10.5,
            fontweight="semibold",
            color=HIGHLIGHT,
            va="bottom",
        )
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
    header(
        fig,
        "Skill against the baseline that matters",
        "Skill = 1 − error(model) / error(persistence). Above zero beats “copy the last value”. Bars: 95% CI.",
        "reports/metrics/headline_metrics.csv, reports/modeling/24h/rolling_origin_backtest.csv",
    )
    ax = fig.add_axes([0.17, 0.12, 0.8, 0.64])
    ax.tick_params(axis="y", length=0)
    y = np.arange(len(rows))[::-1].astype(float)
    for yi, r in zip(y, rows):
        for dy, metric, color, lab in [(0.13, "mae", MODEL, "MAE skill"), (-0.13, "rmse", HIGHLIGHT, "RMSE skill")]:
            s, lo, hi = r[f"skill_{metric}"], r[f"skill_{metric}_ci_lo"], r[f"skill_{metric}_ci_hi"]
            ax.plot([lo, hi], [yi + dy] * 2, color=color, lw=2.2, solid_capstyle="round")
            ax.scatter(
                [s], [yi + dy], s=90, color=color, zorder=3, edgecolor=PAGE, lw=1.5, label=lab if yi == y[0] else None
            )
            ax.text(hi + 0.02, yi + dy, f"{s:+.3f}", va="center", fontsize=10.5, color=color)
    w24 = ro.loc["winter_2024"]
    ax.plot([w24.skill_mae_ci_lo, w24.skill_mae_ci_hi], [y[-1] - 0.4] * 2, color=MUTED, lw=2.2)
    ax.scatter(
        [w24.skill_mae],
        [y[-1] - 0.4],
        s=70,
        color=MUTED,
        zorder=3,
        edgecolor=PAGE,
        lw=1.5,
        label="MAE skill, 2024 winter backtest",
    )
    ax.text(w24.skill_mae_ci_hi + 0.02, y[-1] - 0.4, f"{w24.skill_mae:+.3f}", va="center", fontsize=10.5, color=MUTED)
    ax.axvline(0, color=INK, lw=1)
    ax.text(0.005, y[0] + 0.55, "persistence", fontsize=9.5, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{h} ahead\n{m.split(' (')[0]}" for h, m in models.items()], fontsize=11)
    ax.set_xlim(-1.05, 0.55)
    ax.set_ylim(y[-1] - 0.75, y[0] + 0.75)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", fontsize=10)
    ax.text(
        -1.0,
        y[0] - 0.42,
        "At 1h the model loses on RMSE:\nno real skill once the target is this smooth.",
        fontsize=9.5,
        color=MUTED,
        va="center",
    )
    save(fig, "30_skill_vs_persistence.png")


def fig_extrapolation() -> None:
    tree = pd.read_parquet(DATA / "Artifacts" / "24h" / "predictions_24h_test.parquet")
    hyb = pd.read_parquet(REPORTS / "modeling" / "24h" / "final" / "final_predictions.parquet")
    tree_mae = (tree.y_pred - tree.y_true).abs().mean()
    hyb_mae = (hyb.prediction_hybrid_6c_winning - hyb.target_aqi_24h).abs().mean()
    cap = tree.y_pred.max()

    fig = plt.figure(figsize=(12, 9))
    header(
        fig,
        "The 24-hour failure, and the fix",
        "Trees cannot predict above the highest value they were trained on. Winter went far above it.",
        "data/Artifacts/24h/predictions_24h_test.parquet, reports/modeling/24h/final/final_predictions.parquet",
    )
    axes = [fig.add_axes([0.08, 0.12, 0.4, 0.62]), fig.add_axes([0.56, 0.12, 0.4, 0.62])]
    panels = [
        (axes[0], tree.y_true, tree.y_pred, BASELINE, f"Gradient-boosted trees   MAE {tree_mae:.2f}"),
        (
            axes[1],
            hyb.target_aqi_24h,
            hyb.prediction_hybrid_6c_winning,
            MODEL,
            f"Ridge + persistence hybrid   MAE {hyb_mae:.2f}",
        ),
    ]
    for ax, yt, yp, color, title in panels:
        ax.scatter(yt, yp, s=4, alpha=0.18, color=color, lw=0, rasterized=True)
        ax.plot([0, 520], [0, 520], color=INK, lw=0.8, ls=":")
        ax.axhline(cap, color=HIGHLIGHT, lw=1.4, ls="--")
        ax.set_xlim(100, 510)
        ax.set_ylim(100, 510)
        ax.set_aspect("equal")
        ax.set_xlabel("Actual AQI, 24h later")
        ax.set_title(title, fontsize=12, loc="left", color=INK, pad=10)
    axes[0].set_ylabel("Predicted AQI")
    axes[0].text(108, cap + 8, f"training max ≈ {cap:.0f}: predictions stop here", color=HIGHLIGHT, fontsize=9.5)
    axes[1].text(108, cap + 8, "linear part can go above it", color=HIGHLIGHT, fontsize=9.5)
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
    header(
        fig,
        "What a 24-hour forecast looks like",
        f"{station}, first 30 days of the test winter. Each point is a forecast issued 24 hours earlier.",
        "reports/modeling/24h/final/final_predictions.parquet",
    )
    ax = fig.add_axes([0.08, 0.16, 0.89, 0.58])
    ax.axhspan(401, 520, color=HIGHLIGHT, alpha=0.1, lw=0)
    ax.axhline(401, color=HIGHLIGHT, lw=1, ls="--")
    ax.text(s.target_time.iloc[2], 404, "Severe", color=HIGHLIGHT, fontsize=10, va="bottom")
    ax.plot(s.target_time, s.target_aqi_24h, color=INK, lw=1.8, label="Actual AQI")
    ax.plot(
        s.target_time, s.prediction_naive_persistence, color=BASELINE, lw=1.2, label="Persistence (value 24h earlier)"
    )
    ax.plot(s.target_time, s.prediction_hybrid_6c_winning, color=MODEL, lw=1.8, label="24h hybrid forecast")
    mae_m = (s.prediction_hybrid_6c_winning - s.target_aqi_24h).abs().mean()
    mae_p = (s.prediction_naive_persistence - s.target_aqi_24h).abs().mean()
    ax.text(
        0.99,
        0.04,
        f"MAE in this window: hybrid {mae_m:.1f}, persistence {mae_p:.1f}",
        transform=ax.transAxes,
        ha="right",
        fontsize=10,
        color=MUTED,
    )
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
    header(
        fig,
        "Severe-AQI alerts: recall always has a price",
        "Test winter, 24h ahead. Each curve sweeps the alert cutoff; cutoffs were chosen on validation only.",
        "reports/classification/24h/classified_predictions.parquet, reports/classification/metrics/",
    )
    ax = fig.add_axes([0.1, 0.13, 0.86, 0.62])
    ax.plot(cp[:, 1], cp[:, 2], color=BASELINE, lw=2, label="Persistence")
    ax.plot(cm[:, 1], cm[:, 2], color=MODEL, lw=2.4, label="24h hybrid model")
    points = [
        (401.0, "Statutory 401"),
        (380.0, "Compromise 380"),
        (tau_opt, f"Validation-optimal {tau_opt:g}\n(5:1 cost)"),
    ]
    for t, label in points:
        row = ops[np.isclose(ops.threshold_aqi, t)]
        if row.empty:
            r_ = cm[np.argmin(np.abs(cm[:, 0] - t))]
            rec, prec = r_[1], r_[2]
        else:
            rec, prec = row.test_severe_recall_pct.iloc[0] / 100, row.test_severe_precision_pct.iloc[0] / 100
        ax.scatter([rec], [prec], s=110, color=HIGHLIGHT, zorder=4, edgecolor=PAGE, lw=1.5)
        ax.annotate(
            f"{label}\nrecall {rec:.0%}, precision {prec:.0%}",
            xy=(rec, prec),
            xytext=(-12, -12),
            textcoords="offset points",
            ha="right",
            va="top",
            fontsize=9.5,
            bbox=dict(boxstyle="round,pad=0.3", fc=PAGE, ec="none", alpha=0.9),
        )
    ax.set_xlabel("Recall: share of Severe hours caught")
    ax.set_ylabel("Precision: share of alerts that were right")
    ax.set_xlim(0.45, 1.01)
    ax.set_ylim(0.35, 0.9)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(loc="upper right", fontsize=10.5)

    def precision_at(c, t):
        return c[np.argmin(np.abs(c[:, 0] - t))][2]

    gap = {t: precision_at(cm, t) - precision_at(cp, t) for t in (401.0, 380.0, tau_opt)}
    ax.text(
        0.47,
        0.37,
        f"Model minus persistence precision at the same cutoff: {gap[401.0] * 100:+.1f} points at 401, "
        f"{gap[380.0] * 100:+.1f} at 380, {gap[tau_opt] * 100:+.1f} at {tau_opt:g}.",
        fontsize=10,
        color=MUTED,
    )
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
    header(
        fig,
        "Did the Diwali firecracker ban work? This data can’t tell",
        "Estimated jump in AQI after Diwali 2025, by design. Bars: 95% CI, errors clustered by date.",
        "reports/causal/regression_models_summary.csv",
    )
    ax = fig.add_axes([0.3, 0.22, 0.66, 0.54])
    ax.tick_params(axis="y", length=0)
    ys = np.arange(len(order))[::-1]
    for yi, (key, label) in zip(ys, order):
        row = r.loc[key]
        color = MODEL if "Interrupted" in key else (HIGHLIGHT if "Placebo" in key else BASELINE)
        ax.plot([row.ci_lower, row.ci_upper], [yi, yi], color=color, lw=3, solid_capstyle="round")
        ax.scatter([row.coef], [yi], s=120, color=color, zorder=3, edgecolor=PAGE, lw=1.5)
        p = row.p_value
        ax.text(
            row.ci_upper + 4,
            yi,
            f"{row.coef:+.1f}  (p {'< 0.001' if p < 0.001 else f'= {p:.3f}' if p < 0.01 else f'= {p:.2f}'})",
            va="center",
            fontsize=10.5,
            color=color,
        )
    ax.axvline(0, color=INK, lw=1)
    ax.set_yticks(ys)
    ax.set_yticklabels([lbl for _, lbl in order], fontsize=11)
    ax.set_xlabel("Change in AQI after Diwali")
    ax.set_xlim(-60, 250)
    ax.grid(axis="y", visible=False)
    fig.text(
        0.045,
        0.075,
        f"AQI was already rising {pre.coef:.1f} points/day before Diwali, and a fake event date shows a "
        "“significant” jump, so naive designs mislead.\nThe ban was in force in every year studied, "
        "so there is no untreated year to compare against.",
        fontsize=10,
        color=MUTED,
        va="bottom",
    )
    save(fig, "51_diwali_identification.png")


# ---------------------------------------------------------------------------
# Live system
# ---------------------------------------------------------------------------
def _skill_row(ax, y, s, lo, hi, color, label=None, text_dx=0.02):
    ax.plot([lo, hi], [y, y], color=color, lw=2.4, solid_capstyle="round")
    ax.scatter([s], [y], s=90, color=color, zorder=3, edgecolor=PAGE, lw=1.5, label=label)
    ax.text(hi + text_dx, y, f"{s:+.3f}", va="center", fontsize=10.5, color=color)


def fig_train_serve_skew() -> None:
    m = pd.read_csv(REPORTS / "modeling" / "live_retrain" / "live_retrain_metrics.csv")
    m = m[m.split == "test"]
    horizons = ["1h", "6h", "24h"]
    frozen = m[m.model.str.contains("frozen")].set_index("horizon")
    live = m[(~m.model.str.contains("frozen")) & (m.inputs == "live-masked")].set_index("horizon")

    fig = plt.figure(figsize=(12, 7.5))
    header(
        fig,
        "Train/serve skew: the frozen models do not carry over",
        "Test winter, AQI recomputed from pollutants (what the live feed can compute). Skill vs persistence, 95% CI.",
        "reports/modeling/live_retrain/live_retrain_metrics.csv (test split, scored once)",
    )
    ax = fig.add_axes([0.14, 0.14, 0.82, 0.62])
    ax.tick_params(axis="y", length=0)
    y = np.arange(len(horizons))[::-1].astype(float)
    for yi, h in zip(y, horizons):
        f, v = frozen.loc[h], live.loc[h]
        _skill_row(
            ax,
            yi + 0.14,
            f.skill_mae,
            f.skill_ci_lo,
            f.skill_ci_hi,
            BASELINE,
            "Frozen model (trained on official AQI)" if h == "1h" else None,
        )
        _skill_row(
            ax,
            yi - 0.14,
            v.skill_mae,
            v.skill_ci_lo,
            v.skill_ci_hi,
            MODEL,
            "Live-consistent retrain (live input view)" if h == "1h" else None,
        )
    ax.axvline(0, color=INK, lw=1)
    ax.text(0.005, y[0] + 0.5, "persistence", fontsize=9.5, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{h} ahead" for h in horizons], fontsize=12)
    ax.set_ylim(y[-1] - 0.6, y[0] + 0.65)
    ax.set_xlim(min(frozen.skill_ci_lo.min(), 0) - 0.05, live.skill_ci_hi.max() + 0.12)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("MAE skill vs persistence (right of zero = better than copying the last value)")
    ax.legend(loc="lower left", fontsize=10.5)
    save(fig, "60_train_serve_skew.png")


def fig_baselines_by_horizon() -> None:
    w = pd.read_csv(REPORTS / "modeling" / "live_retrain" / "window_update_baseline.csv")
    w = w[w.split == "test"].set_index("horizon")
    horizons = ["1h", "6h", "24h"]

    fig = plt.figure(figsize=(12, 7.5))
    header(
        fig,
        "A parameter-free rule wins at 1h; the model wins at 6h",
        "Test winter, recomputed AQI. Skill vs plain persistence, 95% CI. The rule is window-update persistence (no fitted parameters).",
        "reports/modeling/live_retrain/window_update_baseline.csv (test split)",
    )
    ax = fig.add_axes([0.25, 0.2, 0.71, 0.56])
    ax.tick_params(axis="y", length=0)
    y = np.arange(len(horizons))[::-1].astype(float)
    labels = []
    for yi, h in zip(y, horizons):
        r = w.loc[h]
        _skill_row(
            ax,
            yi + 0.14,
            r.wu_vs_persistence,
            r.wu_vs_persistence_lo,
            r.wu_vs_persistence_hi,
            HIGHLIGHT,
            "Window-update rule" if h == "1h" else None,
        )
        _skill_row(
            ax,
            yi - 0.14,
            r.model_vs_persistence,
            r.model_vs_persistence_lo,
            r.model_vs_persistence_hi,
            MODEL,
            "LightGBM / hybrid model" if h == "1h" else None,
        )
        labels.append(
            f"{h} ahead\nmodel vs rule {r.model_vs_window_update:+.3f}\n[{r.model_vs_window_update_lo:+.3f}, {r.model_vs_window_update_hi:+.3f}]"
        )
    ax.axvline(0, color=INK, lw=1)
    ax.text(0.005, y[0] + 0.5, "persistence", fontsize=9.5, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5)
    ax.set_ylim(y[-1] - 0.6, y[0] + 0.65)
    ax.set_xlim(
        w.wu_vs_persistence_lo.min() - 0.08, max(w.wu_vs_persistence_hi.max(), w.model_vs_persistence_hi.max()) + 0.14
    )
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("MAE skill vs persistence")
    ax.legend(loc="lower right", fontsize=10.5)
    fig.text(
        0.045,
        0.07,
        "At 24h a flat-hour assumption for a whole day is a poor forecast, so the rule is not a fair comparator there;\n"
        "the 24h claim is the model against plain persistence.",
        fontsize=9.5,
        color=MUTED,
        va="bottom",
    )
    save(fig, "61_baselines_by_horizon.png")


def fig_replay_skill() -> None:
    path = next((REPORTS / "live").glob("replay_*.csv"))
    start, end = re.findall(r"\d{4}-\d{2}-\d{2}", path.name)
    r = pd.read_csv(path)
    names = {"aqi": "AQI", "pm25": "PM2.5"}
    r["label"] = [f"{names[t]} {h}h" for t, h in zip(r.target, r.horizon)]

    fig = plt.figure(figsize=(12, 7.5))
    header(
        fig,
        "Replay skill per live product",
        f"Forecasts re-made hour by hour from stored readings, {start} to {end}. Skill vs persistence, 95% CI. Not a live result.",
        f"reports/live/{path.name}",
    )
    ax = fig.add_axes([0.2, 0.2, 0.76, 0.56])
    ax.tick_params(axis="y", length=0)
    y = np.arange(len(r))[::-1].astype(float)
    for yi, row in zip(y, r.itertuples()):
        color = (
            POSITIVE if row.skill_vs_persistence_lo > 0 else NEGATIVE if row.skill_vs_persistence_hi < 0 else BASELINE
        )
        _skill_row(ax, yi, row.skill_vs_persistence, row.skill_vs_persistence_lo, row.skill_vs_persistence_hi, color)
    ax.axvline(0, color=INK, lw=1)
    ax.text(0.003, y[0] + 0.55, "persistence", fontsize=9.5, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{row.label}\nMAE {row.mae_model:.2f} vs {row.mae_persistence:.2f}, n = {row.n:,}" for row in r.itertuples()],
        fontsize=10.5,
    )
    ax.set_ylim(y[-1] - 0.6, y[0] + 0.8)
    ax.set_xlim(r.skill_vs_persistence_lo.min() - 0.06, r.skill_vs_persistence_hi.max() + 0.12)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("MAE skill vs persistence (grey: interval includes zero)")
    fig.text(
        0.045,
        0.07,
        "AQI 1h is the window-update rule, so its skill vs the rule is zero by construction; the other products are models.",
        fontsize=9.5,
        color=MUTED,
        va="bottom",
    )
    save(fig, "62_replay_skill.png")


def _cron_label(workflow: str) -> str:
    cron = re.search(r'cron:\s*"([^"]+)"', (WORKFLOWS / workflow).read_text()).group(1)
    minute, hour = cron.split()[:2]
    return f"hourly at :{int(minute):02d}" if hour == "*" else f"daily {int(hour):02d}:{int(minute):02d} UTC"


def fig_architecture() -> None:
    fig = plt.figure(figsize=(12, 7.5))
    header(
        fig,
        "How the live system fits together",
        "Scheduled jobs write to one database; a read-only API and the dashboard sit on top. No model server.",
        ".github/workflows/*.yml (schedules), docs/ARCHITECTURE.md, docs/decisions/",
    )
    ax = fig.add_axes([0.02, 0.1, 0.96, 0.72])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, w, h, title, lines, fc=SURFACE, ec=LINE, tc=INK, lc=MUTED):
        card(ax, x, y, w, h, fc=fc, ec=ec)
        ax.text(
            x + 0.012, y + h - 0.035, title, fontfamily=SERIF, fontsize=13.5, fontweight="normal", va="top", color=tc
        )
        for j, line in enumerate(lines):
            ax.text(x + 0.012, y + h - 0.12 - j * 0.07, line, fontsize=9, va="top", color=lc)

    # sources
    box(0.0, 0.62, 0.15, 0.34, "OpenAQ", ["primary source", "hourly station data"])
    box(0.0, 0.2, 0.15, 0.34, "WAQI", ["shadow only", "never feeds forecasts"], fc=HIGHLIGHT_LIGHT, ec=HIGHLIGHT)
    # actions
    card(ax, 0.2, 0.04, 0.26, 0.92, fc=MODEL_LIGHT, ec=MODEL)
    ax.text(0.212, 0.925, "GitHub Actions", fontfamily=SERIF, fontsize=14, fontweight="normal", va="top", color=MODEL)
    jobs = [
        ("ingest", "ingest.yml", "OpenAQ, QC, AQI recompute"),
        ("forecast", "forecast.yml", "rule + hash-pinned models"),
        ("score", "score.yml", "matured forecasts vs actuals"),
        ("shadow ingest", "shadow-waqi.yml", "WAQI into the shadow table"),
    ]
    for k, (name, wf, what) in enumerate(jobs):
        yy = 0.7 - k * 0.2
        card(ax, 0.215, yy - 0.05, 0.23, 0.16, fc=SURFACE, ec=LINE)
        ax.text(0.227, yy + 0.085, name, fontsize=11.5, fontweight="bold", va="top")
        ax.text(0.227, yy + 0.03, _cron_label(wf), fontsize=9.5, va="top", color=HIGHLIGHT)
        ax.text(0.227, yy - 0.015, what, fontsize=9, va="top", color=MUTED)
    # database, api, frontend
    box(0.51, 0.3, 0.165, 0.4, "Supabase", ["Postgres, schema aq", "RLS on every table", "separate write / read roles"])
    box(0.715, 0.3, 0.155, 0.4, "FastAPI", ["Azure Container Apps", "read-only /api/v1", "scale to zero"])
    box(0.91, 0.3, 0.09, 0.4, "React", ["Vercel", "TypeScript", "Vite"], fc=INK, ec=INK, tc=PAGE, lc="#CDD1D5")
    arrow(ax, 0.15, 0.79, 0.215, 0.73, color=MODEL)
    arrow(ax, 0.15, 0.37, 0.215, 0.13, color=HIGHLIGHT)
    arrow(ax, 0.46, 0.5, 0.51, 0.5, color=MODEL)
    arrow(ax, 0.675, 0.5, 0.715, 0.5, color=MODEL)
    arrow(ax, 0.87, 0.5, 0.91, 0.5, color=MODEL)
    save(fig, "10_architecture.png")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    fig_architecture()
    fig_splits_timeline()
    fig_skill()
    fig_extrapolation()
    fig_episode()
    fig_alert_tradeoff()
    fig_diwali()
    fig_train_serve_skew()
    fig_baselines_by_horizon()
    fig_replay_skill()


if __name__ == "__main__":
    main()

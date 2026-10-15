"""
Cost-Aware Risk Classification & Threshold Optimization for 24-Hour AQI Forecasting.

Validation-first protocol (fixes defect D3/D4):
  * The cost-optimal threshold is chosen on the VALIDATION split only.
  * The chosen threshold is then applied to the held-out TEST split exactly once.
  * Recall is always reported together with precision, FPR and the false-alarm
    count, and every operating point is compared against naive persistence.

Formulation:
- Positive class (Severe Event): Actual AQI >= 401
- Decision rule: predict Severe if y_hat >= tau
- False alarm cost C_FP: predicting Severe when actual AQI < 401
- Missed hazard cost C_FN: predicting non-Severe when actual AQI >= 401
- Cost ratio R = C_FN / C_FP (swept from 1:1 to 20:1)
- Expected rate cost: E[cost](tau) = FPR(tau) * 1 + FNR(tau) * R
- Sample-normalized cost: ((FP * 1) + (FN * R)) / N

Artifacts (paths consumed by dashboard/app.py and backend/main.py are unchanged):
- reports/classification/metrics/cost_threshold_sweep_24h.csv          (validation sweep)
- reports/classification/metrics/cost_optimal_thresholds_summary.csv   (selected_on = val)
- reports/classification/metrics/threshold_operating_points_comparison.csv
- reports/classification/figures/01..04_*.png
- reports/modeling/24h/final/val_predictions.parquet                   (new)
"""

import os

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, precision_recall_curve

plt.style.use("default")
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["font.size"] = 11
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["axes.labelsize"] = 12
plt.rcParams["figure.titlesize"] = 15
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.4
plt.rcParams["grid.linestyle"] = "--"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEVERE_THRESHOLD = 401.0
TAU_MIN, TAU_MAX, TAU_STEP = 200.0, 500.0, 0.5
COST_RATIOS = [1.0, 2.0, 3.0, 5.0, 10.0, 20.0]

MODEL_COL = "prediction_hybrid_6c_winning"
PERSIST_COL = "prediction_naive_persistence"
TRUTH_COL = "target_aqi_24h"

SWEEP_CSV = os.path.join(REPO_ROOT, "reports/classification/metrics/cost_threshold_sweep_24h.csv")
SUMMARY_CSV = os.path.join(REPO_ROOT, "reports/classification/metrics/cost_optimal_thresholds_summary.csv")
OPERATING_CSV = os.path.join(REPO_ROOT, "reports/classification/metrics/threshold_operating_points_comparison.csv")
VAL_PREDS = os.path.join(REPO_ROOT, "reports/modeling/24h/final/val_predictions.parquet")
FIG_DIR = os.path.join(REPO_ROOT, "reports/classification/figures")


# ---------------------------------------------------------------------------
# 1. Rebuild validation / test predictions from the frozen 24h artifact
# ---------------------------------------------------------------------------
def build_predictions():
    """Recompute the frozen Phase 6C hybrid on val and test, verify test, return both."""
    import sys

    sys.path.insert(0, os.path.join(REPO_ROOT, "src/models"))
    from phase_6c_refinement import construct_causal_long_horizon_features

    df_24h = pd.read_parquet(os.path.join(REPO_ROOT, "data/processed/ml/air_quality_ml_24h_v1.parquet"))
    df_feat = pd.read_parquet(os.path.join(REPO_ROOT, "data/processed/features_2025.parquet"))
    augmented = construct_causal_long_horizon_features(df_feat)
    new_cols = [c for c in augmented.columns if c not in df_24h.columns]
    merged = df_24h.merge(
        augmented[["station_id", "station_name", "timestamp"] + new_cols],
        on=["station_id", "station_name", "timestamp"],
        how="inner",
    )

    final_dir = os.path.join(REPO_ROOT, "models/24h/final")
    feats = joblib.load(os.path.join(final_dir, "feature_names_final.joblib"))
    imputer = joblib.load(os.path.join(final_dir, "imputer_final_24h.joblib"))
    scaler = joblib.load(os.path.join(final_dir, "scaler_final_24h.joblib"))
    model = joblib.load(os.path.join(final_dir, "24h_final_model.joblib"))

    missing = [f for f in feats if f not in merged.columns]
    if missing:
        raise KeyError(f"Frozen feature list references missing columns: {missing}")

    frames = {}
    for split in ("val", "test"):
        d = merged[merged["split"] == split].copy()
        X = scaler.transform(imputer.transform(d[feats]))
        ridge = model.predict(X)
        d["pred_ridge"] = ridge
        # Blend is 0.5 * persistence + 0.5 * ridge (see phase_6c_refinement.py:359).
        d[MODEL_COL] = 0.5 * d["aqi_curr"].to_numpy() + 0.5 * ridge
        d[PERSIST_COL] = d["aqi_curr"].to_numpy()
        frames[split] = d

    # Verify the reconstruction reproduces the frozen test predictions exactly.
    ref = pd.read_parquet(os.path.join(REPO_ROOT, "reports/modeling/24h/final/final_predictions.parquet"))
    check = frames["test"].merge(
        ref[["station_id", "timestamp", MODEL_COL]], on=["station_id", "timestamp"], how="inner"
    )
    max_diff = float(np.abs(check[MODEL_COL + "_x"] - check[MODEL_COL + "_y"]).max()) if len(check) else float("nan")
    print(f"  Frozen-artifact check: {len(check)} test rows matched, max |diff| = {max_diff:.6f}")
    if not (len(check) and max_diff < 1e-6):
        raise AssertionError("Reconstructed test predictions do not match the frozen artifact.")

    out_cols = ["station_id", "station_name", "timestamp", "split", "aqi_curr", TRUTH_COL, MODEL_COL, PERSIST_COL]
    val_out = frames["val"][out_cols].reset_index(drop=True)
    val_out.to_parquet(VAL_PREDS, index=False)
    print(f"  Saved: {os.path.relpath(VAL_PREDS, REPO_ROOT)} ({len(val_out)} val rows)")
    return val_out, frames["test"][out_cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Threshold sweep and cost selection
# ---------------------------------------------------------------------------
def confusion_at(y_true, y_pred, tau):
    """Binary confusion metrics for threshold tau, plus the false-alarm mix."""
    actual_pos = y_true >= SEVERE_THRESHOLD
    pred_pos = y_pred >= tau
    tp = int((pred_pos & actual_pos).sum())
    fp = int((pred_pos & ~actual_pos).sum())
    fn = int((~pred_pos & actual_pos).sum())
    tn = int((~pred_pos & ~actual_pos).sum())
    n_pos, n_neg = int(actual_pos.sum()), int((~actual_pos).sum())

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / n_neg if n_neg else 0.0
    fnr = fn / n_pos if n_pos else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "fnr": fnr,
        "fp_actual_vpoor": int((pred_pos & (y_true >= 301) & (y_true <= 400)).sum()),
        "fp_actual_poor": int((pred_pos & (y_true >= 201) & (y_true <= 300)).sum()),
        "fp_actual_mod_better": int((pred_pos & (y_true <= 200)).sum()),
    }


def run_threshold_sweep(df):
    """Sweep tau on the given split for both the model and persistence."""
    y_true = df[TRUTH_COL].to_numpy(dtype=float)
    y_model = df[MODEL_COL].to_numpy(dtype=float)
    y_persist = df[PERSIST_COL].to_numpy(dtype=float)
    total_n = len(y_true)

    records = []
    for tau in np.arange(TAU_MIN, TAU_MAX + TAU_STEP, TAU_STEP):
        m = confusion_at(y_true, y_model, tau)
        p = confusion_at(y_true, y_persist, tau)
        row = {
            "threshold": tau,
            "selected_on": "val",
            **m,
            "persist_tp": p["tp"],
            "persist_fp": p["fp"],
            "persist_fn": p["fn"],
            "persist_recall": p["recall"],
            "persist_precision": p["precision"],
            "persist_fpr": p["fpr"],
            "persist_fnr": p["fnr"],
        }
        for r in COST_RATIOS:
            row[f"cost_rate_{int(r)}x"] = m["fpr"] * 1.0 + m["fnr"] * r
            row[f"cost_sample_{int(r)}x"] = (m["fp"] * 1.0 + m["fn"] * r) / total_n
        records.append(row)
    return pd.DataFrame(records)


def select_thresholds_on_val(val_sweep):
    """Pick the cost-minimizing threshold per ratio using validation cost only."""
    rows = []
    cpcb_val = val_sweep.iloc[(val_sweep["threshold"] - SEVERE_THRESHOLD).abs().argmin()]
    for r in COST_RATIOS:
        col = f"cost_rate_{int(r)}x"
        opt = val_sweep.loc[val_sweep[col].idxmin()]
        rows.append(
            {
                "cost_ratio_fn_to_fp": f"{int(r)}:1",
                "ratio_val": r,
                "selected_on": "val",
                "optimal_threshold": float(opt["threshold"]),
                "threshold_shift_vs_401": float(opt["threshold"] - SEVERE_THRESHOLD),
                "val_cost_rate": float(opt[col]),
                "cpcb_401_val_cost_rate": float(cpcb_val[col]),
                "cost_rate_reduction_pct": float((cpcb_val[col] - opt[col]) / cpcb_val[col] * 100),
            }
        )
    return pd.DataFrame(rows), cpcb_val


def apply_selected_thresholds(summary, val, test, val_sweep):
    """Apply each validation-selected threshold to test exactly once (model + persistence)."""
    out = []
    for _, s in summary.iterrows():
        tau = float(s["optimal_threshold"])
        ratio = s["ratio_val"]

        vm = confusion_at(val[TRUTH_COL].to_numpy(), val[MODEL_COL].to_numpy(), tau)
        tm = confusion_at(test[TRUTH_COL].to_numpy(), test[MODEL_COL].to_numpy(), tau)
        tp_ = confusion_at(test[TRUTH_COL].to_numpy(), test[PERSIST_COL].to_numpy(), tau)

        col = f"cost_rate_{int(ratio)}x"
        cpcb_test = confusion_at(test[TRUTH_COL].to_numpy(), test[MODEL_COL].to_numpy(), SEVERE_THRESHOLD)
        cpcb_cost = cpcb_test["fpr"] * 1.0 + cpcb_test["fnr"] * ratio
        test_cost = tm["fpr"] * 1.0 + tm["fnr"] * ratio

        row = dict(s)
        for prefix, m in (("val", vm), ("test", tm)):
            for key in ("tp", "fp", "fn", "tn", "precision", "recall", "f1", "fpr", "fnr"):
                row[f"{prefix}_{key}"] = m[key]
        row["test_cost_rate"] = test_cost
        row["test_cpcb_401_recall"] = cpcb_test["recall"]
        row["test_cpcb_401_precision"] = cpcb_test["precision"]
        row["test_cpcb_401_fpr"] = cpcb_test["fpr"]
        row["test_cpcb_401_fp"] = cpcb_test["fp"]
        row["test_cost_rate_reduction_pct"] = (cpcb_cost - test_cost) / cpcb_cost * 100
        for key in ("tp", "fp", "fn", "precision", "recall", "fpr", "fnr"):
            row[f"persistence_test_{key}"] = tp_[key]
        out.append(row)
    return pd.DataFrame(out)


def export_operating_points(val_sweep, test, test_summary):
    """Compare standard operating points on validation, then verify on test."""
    test_y = test[TRUTH_COL].to_numpy(dtype=float)
    test_model = test[MODEL_COL].to_numpy(dtype=float)
    test_persist = test[PERSIST_COL].to_numpy(dtype=float)
    points = [401.0, 390.0, 380.0, 360.0, 341.0, 324.0, 300.0]
    rows = []
    for pt in points:
        idx = (val_sweep["threshold"] - pt).abs().argmin()
        r = val_sweep.iloc[idx]
        tau = float(r["threshold"])
        tm = confusion_at(test_y, test_model, tau)
        tp_ = confusion_at(test_y, test_persist, tau)
        rows.append(
            {
                "threshold_aqi": tau,
                "selected_on": "val",
                "severe_recall_pct": r["recall"] * 100,
                "severe_precision_pct": r["precision"] * 100,
                "severe_f1_pct": r["f1"] * 100,
                "false_alarm_rate_fpr_pct": r["fpr"] * 100,
                "missed_rate_fnr_pct": r["fnr"] * 100,
                "true_severe_caught_h": int(r["tp"]),
                "severe_missed_h": int(r["fn"]),
                "false_alarms_total_h": int(r["fp"]),
                "false_alarms_actual_vpoor_h": int(r["fp_actual_vpoor"]),
                "false_alarms_actual_poor_h": int(r["fp_actual_poor"]),
                "false_alarms_actual_mod_better_h": int(r["fp_actual_mod_better"]),
                "test_severe_recall_pct": tm["recall"] * 100,
                "test_severe_precision_pct": tm["precision"] * 100,
                "test_false_alarm_rate_fpr_pct": tm["fpr"] * 100,
                "test_true_severe_caught_h": int(tm["tp"]),
                "test_severe_missed_h": int(tm["fn"]),
                "test_false_alarms_total_h": int(tm["fp"]),
                "persistence_test_severe_recall_pct": tp_["recall"] * 100,
                "persistence_test_severe_precision_pct": tp_["precision"] * 100,
                "persistence_test_fpr_pct": tp_["fpr"] * 100,
                "cost_rate_1x": r["cost_rate_1x"],
                "cost_rate_5x": r["cost_rate_5x"],
                "cost_rate_10x": r["cost_rate_10x"],
                "sample_cost_5x": r["cost_sample_5x"],
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Figures (regenerated from the validation sweep)
# ---------------------------------------------------------------------------
def plot_precision_recall_curve(sweep_df, val_df, cpcb_row, opt_summary, split_label="validation"):
    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
    y_true = (val_df[TRUTH_COL] >= SEVERE_THRESHOLD).values
    y_pred = val_df[MODEL_COL].values
    prec, rec, _ = precision_recall_curve(y_true, y_pred)
    auprc = average_precision_score(y_true, y_pred)
    ax.plot(rec, prec, color="#1f77b4", linewidth=2.8, label=f"24h Model PR Curve (AUPRC = {auprc:.4f})")
    ax.axhline(
        y_true.mean(),
        color="gray",
        linestyle="--",
        linewidth=1.2,
        label=f"No-Skill Baseline (Prevalence = {y_true.mean():.1%})",
    )
    ax.scatter(
        cpcb_row["recall"],
        cpcb_row["precision"],
        color="#d62728",
        s=160,
        zorder=5,
        edgecolor="black",
        linewidth=1.5,
        label=f"Fixed CPCB Breakpoint (tau=401)\n  Rec={cpcb_row['recall']:.1%}, Prec={cpcb_row['precision']:.1%}",
    )
    opt_5x = opt_summary[opt_summary["ratio_val"] == 5.0].iloc[0]
    sel = sweep_df.iloc[(sweep_df["threshold"] - opt_5x["optimal_threshold"]).abs().argmin()]
    ax.scatter(
        sel["recall"],
        sel["precision"],
        color="#2ca02c",
        s=160,
        zorder=5,
        edgecolor="black",
        linewidth=1.5,
        label=f"Val-selected 5:1 (tau={opt_5x['optimal_threshold']:.0f})\n  Rec={sel['recall']:.1%}, Prec={sel['precision']:.1%}",
    )
    ax.set_title(
        f"24-Hour Severe AQI (>=401) Precision-Recall Curve ({split_label} selection)\nFixed CPCB Breakpoint vs. Cost-Aware Thresholds",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Recall (Severe Exceedance Detection Rate)", fontweight="bold")
    ax.set_ylabel("Precision (Positive Predictive Value)", fontweight="bold")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0.0, 1.02)
    ax.legend(loc="lower left", frameon=True, fontsize=9, shadow=True)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "01_precision_recall_curve_24h.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"  Saved: {os.path.relpath(path, REPO_ROOT)}")


def plot_expected_cost_vs_threshold(sweep_df, opt_summary, cpcb_row, split_label="validation"):
    fig, ax = plt.subplots(figsize=(11, 7), dpi=300)
    palette = {
        1.0: ("#9467bd", "1:1 (Symmetric Cost)"),
        2.0: ("#17becf", "2:1 (Moderate Health Priority)"),
        3.0: ("#e377c2", "3:1 (High Health Priority)"),
        5.0: ("#2ca02c", "5:1 (Baseline Health Priority)"),
        10.0: ("#d62728", "10:1 (Emergency Crisis Priority)"),
    }
    for r, (color, label) in palette.items():
        col = f"cost_rate_{int(r)}x"
        ax.plot(sweep_df["threshold"], sweep_df[col], color=color, linewidth=2.2, label=label)
        opt_r = opt_summary[opt_summary["ratio_val"] == r].iloc[0]
        ax.scatter(opt_r["optimal_threshold"], opt_r["val_cost_rate"], color=color, s=90, zorder=5, edgecolor="black")
    ax.axvline(
        SEVERE_THRESHOLD, color="#d62728", linestyle="--", linewidth=2.0, label="Statutory CPCB Breakpoint (tau = 401)"
    )
    opt_5x = opt_summary[opt_summary["ratio_val"] == 5.0].iloc[0]
    ax.annotate(
        f"Val-optimal tau = {opt_5x['optimal_threshold']:.0f}\nMin cost = {opt_5x['val_cost_rate']:.3f}\n(-{opt_5x['cost_rate_reduction_pct']:.1f}% vs CPCB 401)",
        xy=(opt_5x["optimal_threshold"], opt_5x["val_cost_rate"]),
        xytext=(opt_5x["optimal_threshold"] - 70, opt_5x["val_cost_rate"] + 0.4),
        arrowprops=dict(facecolor="#2ca02c", shrink=0.08, width=1.5, headwidth=7),
        fontweight="bold",
        color="#196F3D",
        bbox=dict(boxstyle="round,pad=0.3", fc="#e8f8f5", ec="#2ca02c", lw=1.2),
    )
    ax.set_title(
        f"Expected Rate Cost vs. Severe Threshold ({split_label} data)\nExpected Cost = FPR * 1.0 + FNR * (Cost Ratio)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Severe Classification Decision Threshold tau (Predicted AQI)", fontweight="bold")
    ax.set_ylabel("Expected Rate Cost per Sample Opportunity", fontweight="bold")
    ax.set_xlim(260, 470)
    ax.legend(loc="upper right", frameon=True, fontsize=9, shadow=True)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "02_expected_cost_vs_threshold.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"  Saved: {os.path.relpath(path, REPO_ROOT)}")


def plot_tradeoff_metrics(sweep_df, cpcb_row, opt_summary, split_label="validation"):
    fig, axs = plt.subplots(2, 2, figsize=(14, 10), dpi=300)
    tau5 = float(opt_summary[opt_summary["ratio_val"] == 5.0]["optimal_threshold"].iloc[0])

    axs[0, 0].plot(
        sweep_df["threshold"],
        sweep_df["recall"] * 100,
        color="#2ca02c",
        linewidth=2.5,
        label="Recall (Severe Sensitivity %)",
    )
    axs[0, 0].plot(
        sweep_df["threshold"], sweep_df["precision"] * 100, color="#1f77b4", linewidth=2.5, label="Precision (PPV %)"
    )
    axs[0, 0].plot(
        sweep_df["threshold"], sweep_df["f1"] * 100, color="#9467bd", linewidth=2.0, linestyle="-.", label="Severe F1 %"
    )
    axs[0, 0].axvline(SEVERE_THRESHOLD, color="#d62728", linestyle="--", linewidth=1.5, label="CPCB 401")
    axs[0, 0].axvline(tau5, color="#2ca02c", linestyle=":", linewidth=1.8, label=f"Val 5:1 optimal ({tau5:.0f})")
    axs[0, 0].set_title("(A) Precision, Recall & F1 Trade-off", fontweight="bold")
    axs[0, 0].set_xlabel("Decision Threshold tau (AQI)")
    axs[0, 0].set_ylabel("Percentage (%)")
    axs[0, 0].legend(loc="lower left", fontsize=8)

    axs[0, 1].plot(
        sweep_df["threshold"], sweep_df["fpr"] * 100, color="#ff7f0e", linewidth=2.5, label="False Alarm Rate (FPR %)"
    )
    axs[0, 1].plot(
        sweep_df["threshold"], sweep_df["fnr"] * 100, color="#d62728", linewidth=2.5, label="Missed Hazard Rate (FNR %)"
    )
    axs[0, 1].axvline(SEVERE_THRESHOLD, color="#d62728", linestyle="--", linewidth=1.5)
    axs[0, 1].axvline(tau5, color="#2ca02c", linestyle=":", linewidth=1.8)
    axs[0, 1].set_title("(B) Error Rates: False Alarm vs. Missed Crisis", fontweight="bold")
    axs[0, 1].set_xlabel("Decision Threshold tau (AQI)")
    axs[0, 1].set_ylabel("Error Rate (%)")
    axs[0, 1].legend(loc="upper center", fontsize=9)

    axs[1, 0].plot(
        sweep_df["threshold"], sweep_df["tp"], color="#2ca02c", linewidth=2.5, label="True Severe Caught (h)"
    )
    axs[1, 0].plot(sweep_df["threshold"], sweep_df["fn"], color="#d62728", linewidth=2.5, label="Severe Missed (h)")
    axs[1, 0].axvline(SEVERE_THRESHOLD, color="#d62728", linestyle="--", linewidth=1.5)
    axs[1, 0].axvline(tau5, color="#2ca02c", linestyle=":", linewidth=1.8)
    axs[1, 0].set_title("(C) Severe Event Counts", fontweight="bold")
    axs[1, 0].set_xlabel("Decision Threshold tau (AQI)")
    axs[1, 0].set_ylabel("Hours")
    axs[1, 0].legend(loc="center right", fontsize=9)

    axs[1, 1].plot(
        sweep_df["threshold"],
        sweep_df["fp_actual_vpoor"],
        color="#d95f02",
        linewidth=2.5,
        label="Actual Very Poor (301-400)",
    )
    axs[1, 1].plot(
        sweep_df["threshold"], sweep_df["fp_actual_poor"], color="#7570b3", linewidth=2.2, label="Actual Poor (201-300)"
    )
    axs[1, 1].plot(
        sweep_df["threshold"],
        sweep_df["fp_actual_mod_better"],
        color="#1b9e77",
        linewidth=2.0,
        label="Actual Moderate or better (<=200)",
    )
    axs[1, 1].axvline(SEVERE_THRESHOLD, color="#d62728", linestyle="--", linewidth=1.5)
    axs[1, 1].axvline(tau5, color="#2ca02c", linestyle=":", linewidth=1.8)
    axs[1, 1].set_title("(D) Composition of False Alarms", fontweight="bold")
    axs[1, 1].set_xlabel("Decision Threshold tau (AQI)")
    axs[1, 1].set_ylabel("False Alarm Hours")
    axs[1, 1].legend(loc="upper right", fontsize=8)

    fig.suptitle(f"(Selection on {split_label}; test reported separately)", fontsize=11)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "03_tradeoff_metrics_vs_threshold.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"  Saved: {os.path.relpath(path, REPO_ROOT)}")


def plot_false_positive_composition(sweep_df, opt_summary, split_label="validation"):
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    sub = sweep_df[(sweep_df["threshold"] >= 280) & (sweep_df["threshold"] <= 440)]
    tau5 = float(opt_summary[opt_summary["ratio_val"] == 5.0]["optimal_threshold"].iloc[0])
    ax.plot(
        sub["threshold"],
        sub["fp_actual_vpoor"],
        color="#d95f02",
        linewidth=2.5,
        label="Actual Very Poor (301-400) [GRAP II]",
    )
    ax.plot(
        sub["threshold"], sub["fp_actual_poor"], color="#7570b3", linewidth=2.2, label="Actual Poor (201-300) [GRAP I]"
    )
    ax.plot(
        sub["threshold"],
        sub["fp_actual_mod_better"],
        color="#1b9e77",
        linewidth=2.0,
        label="Actual Moderate or better (<=200)",
    )
    ax.axvline(SEVERE_THRESHOLD, color="#d62728", linestyle="--", linewidth=1.8, label="CPCB 401 Breakpoint")
    ax.axvline(tau5, color="#2ca02c", linestyle=":", linewidth=1.8, label=f"Val 5:1 optimal ({tau5:.0f})")
    ax.set_title(
        f"Anatomy of False Alarms ({split_label} data)\nWhat Air Quality Was Actually Present?",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Decision Threshold tau (AQI)", fontweight="bold")
    ax.set_ylabel("False Alarm Hours (Count)", fontweight="bold")
    ax.set_xlim(280, 440)
    ax.legend(loc="upper right", frameon=True, fontsize=9, shadow=True)
    plt.tight_layout()
    path = os.path.join(FIG_DIR, "04_false_positive_composition.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"  Saved: {os.path.relpath(path, REPO_ROOT)}")


# ---------------------------------------------------------------------------
# 4. Orchestration
# ---------------------------------------------------------------------------
def main():
    os.makedirs(os.path.dirname(SWEEP_CSV), exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    print("=" * 80)
    print("Validation-first cost-aware threshold analysis (24h horizon)")
    print("=" * 80)

    print("\n[1/6] Rebuilding frozen 24h predictions...")
    val, test = build_predictions()
    print(f"  Val rows: {len(val)} | Test rows: {len(test)}")

    print("\n[2/6] Sweeping thresholds on VALIDATION...")
    val_sweep = run_threshold_sweep(val)
    val_sweep.to_csv(SWEEP_CSV, index=False)
    print(f"  Saved: {os.path.relpath(SWEEP_CSV, REPO_ROOT)} ({len(val_sweep)} thresholds, selected_on=val)")

    print("\n[3/6] Selecting cost-optimal thresholds on validation only...")
    summary, cpcb_val = select_thresholds_on_val(val_sweep)
    summary = apply_selected_thresholds(summary, val, test, val_sweep)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(f"  Saved: {os.path.relpath(SUMMARY_CSV, REPO_ROOT)}")

    print("\n[4/6] Comparing standard operating points...")
    operating = export_operating_points(val_sweep, test, summary)
    operating.to_csv(OPERATING_CSV, index=False)
    print(f"  Saved: {os.path.relpath(OPERATING_CSV, REPO_ROOT)}")

    print("\n[5/6] Regenerating figures...")
    plot_precision_recall_curve(val_sweep, val, cpcb_val, summary)
    plot_expected_cost_vs_threshold(val_sweep, summary, cpcb_val)
    plot_tradeoff_metrics(val_sweep, cpcb_val, summary)
    plot_false_positive_composition(val_sweep, summary)

    print("\n[6/6] Validation-selected thresholds and their one-shot test evaluation")
    show = summary[
        [
            "cost_ratio_fn_to_fp",
            "optimal_threshold",
            "val_recall",
            "val_precision",
            "val_fpr",
            "val_fp",
            "test_recall",
            "test_precision",
            "test_fpr",
            "test_fp",
        ]
    ]
    print(show.to_string(index=False))

    print("\nPersistence baseline at the same thresholds (test):")
    pers = summary[
        [
            "cost_ratio_fn_to_fp",
            "optimal_threshold",
            "persistence_test_recall",
            "persistence_test_precision",
            "persistence_test_fpr",
            "persistence_test_fp",
        ]
    ]
    print(pers.to_string(index=False))

    print("\nAll validation-first cost-aware artifacts generated successfully!")


if __name__ == "__main__":
    main()

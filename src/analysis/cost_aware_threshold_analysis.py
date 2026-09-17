"""
Cost-Aware Risk Classification & Threshold Optimization for 24-Hour AQI Forecasting.

This module reframes Phase 7 discrete CPCB risk classification using an explicit asymmetric
loss / cost ratio formulation rather than applying fixed statutory breakpoints (AQI >= 401) uncritically.

Formulation:
- Positive class (Severe Event): Actual AQI >= 401
- Decision Rule: Predict Severe if y_hat >= tau
- False Alarm Cost (C_FP): Cost of predicting Severe when actual AQI < 401 (operational disruption, transit bans, construction stoppage)
- Missed Hazardous Cost (C_FN): Cost of predicting non-Severe when actual AQI >= 401 (unmitigated toxic exposure, emergency room admissions)
- Cost Ratio: R = C_FN / C_FP (Default baseline = 5:1, swept from 1:1 to 20:1)
- Expected Rate Cost: Expected_Cost(tau) = FPR(tau) * C_FP + FNR(tau) * C_FN
- Sample Normalized Cost: Total_Cost(tau) = (FP(tau) * C_FP + FN(tau) * C_FN) / N
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, average_precision_score, roc_curve, auc

# Set clean aesthetic styling
plt.style.use('default')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['figure.titlesize'] = 15
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.4
plt.rcParams['grid.linestyle'] = '--'

os.makedirs('reports/classification/figures', exist_ok=True)
os.makedirs('reports/classification/metrics', exist_ok=True)


def load_data():
    """Load the held-out test predictions for 24h horizon."""
    path_24h = 'reports/classification/24h/classified_predictions.parquet'
    if not os.path.exists(path_24h):
        raise FileNotFoundError(f"Missing 24h prediction parquet at {path_24h}")

    df_24h = pd.read_parquet(path_24h)
    return df_24h


def run_threshold_sweep(df: pd.DataFrame,
                        actual_col: str = 'target_aqi_24h',
                        pred_col: str = 'prediction_hybrid_6c_winning',
                        tau_min: float = 200.0,
                        tau_max: float = 500.0,
                        step: float = 0.5):
    """
    Sweep classification threshold tau across [tau_min, tau_max] and compute
    binary confusion metrics, rates, and costs for Severe detection (AQI >= 401).
    """
    y_true = df[actual_col].values
    y_pred = df[pred_col].values

    actual_pos = (y_true >= 401)
    actual_neg = ~actual_pos
    n_pos = int(actual_pos.sum())
    n_neg = int(actual_neg.sum())
    total_n = len(y_true)

    thresholds = np.arange(tau_min, tau_max + step, step)
    records = []

    cost_ratios = [1.0, 2.0, 3.0, 5.0, 10.0, 20.0]

    for tau in thresholds:
        pred_pos = (y_pred >= tau)
        pred_neg = ~pred_pos

        tp = int((pred_pos & actual_pos).sum())
        fp = int((pred_pos & actual_neg).sum())
        fn = int((pred_neg & actual_pos).sum())
        tn = int((pred_neg & actual_neg).sum())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / n_neg if n_neg > 0 else 0.0
        fnr = fn / n_pos if n_pos > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        # Breakdown of False Positives by actual underlying CPCB category
        fp_vpoor = int((pred_pos & (y_true >= 301) & (y_true <= 400)).sum())
        fp_poor = int((pred_pos & (y_true >= 201) & (y_true <= 300)).sum())
        fp_mod_better = int((pred_pos & (y_true <= 200)).sum())

        # Breakdown of False Negatives by predicted category
        fn_vpoor = int((pred_neg & (y_pred >= 301) & (y_pred <= 400) & actual_pos).sum())
        fn_poor = int((pred_neg & (y_pred >= 201) & (y_pred <= 300) & actual_pos).sum())
        fn_mod_better = int((pred_neg & (y_pred <= 200) & actual_pos).sum())

        row = {
            'threshold': tau,
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': prec, 'recall': rec, 'f1': f1,
            'fpr': fpr, 'fnr': fnr,
            'fp_actual_vpoor': fp_vpoor,
            'fp_actual_poor': fp_poor,
            'fp_actual_mod_better': fp_mod_better,
            'fn_pred_vpoor': fn_vpoor,
            'fn_pred_poor': fn_poor,
            'fn_pred_mod_better': fn_mod_better,
        }

        for r in cost_ratios:
            # Expected cost on rate basis (FPR * 1 + FNR * r)
            row[f'cost_rate_{int(r)}x'] = fpr * 1.0 + fnr * r
            # Sample-normalized total cost ((FP * 1 + FN * r) / N)
            row[f'cost_sample_{int(r)}x'] = (fp * 1.0 + fn * r) / total_n

        records.append(row)

    sweep_df = pd.DataFrame(records)
    return sweep_df, n_pos, n_neg, total_n


def find_cost_optimal_thresholds(sweep_df: pd.DataFrame):
    """Find the optimal threshold that minimizes expected cost for each cost ratio."""
    cost_ratios = [1.0, 2.0, 3.0, 5.0, 10.0, 20.0]
    summary_records = []

    # Also evaluate fixed statutory CPCB threshold (tau = 401.0)
    cpcb_row = sweep_df.iloc[(sweep_df['threshold'] - 401.0).abs().argmin()]

    for r in cost_ratios:
        r_int = int(r)
        col_rate = f'cost_rate_{r_int}x'
        col_sample = f'cost_sample_{r_int}x'

        opt_idx = sweep_df[col_rate].idxmin()
        opt_row = sweep_df.loc[opt_idx]

        cpcb_cost_rate = cpcb_row[col_rate]
        cpcb_cost_sample = cpcb_row[col_sample]

        rate_saving_pct = (cpcb_cost_rate - opt_row[col_rate]) / cpcb_cost_rate * 100
        sample_saving_pct = (cpcb_cost_sample - opt_row[col_sample]) / cpcb_cost_sample * 100

        summary_records.append({
            'cost_ratio_fn_to_fp': f'{r_int}:1',
            'ratio_val': r,
            'optimal_threshold': opt_row['threshold'],
            'threshold_shift_vs_401': opt_row['threshold'] - 401.0,
            'optimal_recall': opt_row['recall'],
            'optimal_precision': opt_row['precision'],
            'optimal_f1': opt_row['f1'],
            'optimal_fpr': opt_row['fpr'],
            'optimal_fnr_miss_rate': opt_row['fnr'],
            'optimal_tp': opt_row['tp'],
            'optimal_fp': opt_row['fp'],
            'optimal_fn': opt_row['fn'],
            'optimal_tn': opt_row['tn'],
            'optimal_cost_rate': opt_row[col_rate],
            'cpcb_401_cost_rate': cpcb_cost_rate,
            'cost_rate_reduction_pct': rate_saving_pct,
            'optimal_cost_sample': opt_row[col_sample],
            'cpcb_401_cost_sample': cpcb_cost_sample,
            'cost_sample_reduction_pct': sample_saving_pct,
        })

    return pd.DataFrame(summary_records), cpcb_row


def plot_precision_recall_curve(sweep_df: pd.DataFrame,
                                df_24h: pd.DataFrame,
                                cpcb_row: pd.Series,
                                opt_summary: pd.DataFrame):
    """Plot 1: Precision-Recall Curve for 24h Severe Classification."""
    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)

    y_true = (df_24h['target_aqi_24h'] >= 401).values
    y_pred = df_24h['prediction_hybrid_6c_winning'].values

    sk_prec, sk_rec, sk_thresh = precision_recall_curve(y_true, y_pred)
    auprc = average_precision_score(y_true, y_pred)

    # Plot PR curve
    ax.plot(sk_rec, sk_prec, color='#1f77b4', linewidth=2.8,
            label=f'24h Model PR Curve (AUPRC = {auprc:.4f})')

    # Baseline prevalence
    prev = y_true.mean()
    ax.axhline(prev, color='gray', linestyle='--', linewidth=1.2,
               label=f'No-Skill Baseline (Prevalence = {prev:.1%})')

    # Mark Key Operating Points
    # 1. Statutory CPCB Breakpoint (tau = 401)
    ax.scatter(cpcb_row['recall'], cpcb_row['precision'], color='#d62728', s=160, zorder=5,
               edgecolor='black', linewidth=1.5,
               label=f"Fixed CPCB Breakpoint (tau=401)\n  Rec={cpcb_row['recall']:.1%}, Prec={cpcb_row['precision']:.1%}")
    ax.annotate(f"tau = 401\n(Rec={cpcb_row['recall']:.1%}, Prec={cpcb_row['precision']:.1%})",
                xy=(cpcb_row['recall'], cpcb_row['precision']),
                xytext=(cpcb_row['recall'] - 0.22, cpcb_row['precision'] + 0.08),
                arrowprops=dict(facecolor='#d62728', shrink=0.08, width=1.5, headwidth=8),
                fontweight='bold', color='#900C3F', bbox=dict(boxstyle='round,pad=0.3', fc='#ffe6e6', ec='#d62728', lw=1.2))

    # 2. Cost-Optimal 5:1 Point (tau = 341)
    opt_5x = opt_summary[opt_summary['ratio_val'] == 5.0].iloc[0]
    ax.scatter(opt_5x['optimal_recall'], opt_5x['optimal_precision'], color='#2ca02c', s=160, zorder=5,
               edgecolor='black', linewidth=1.5,
               label=f"Cost-Optimal 5:1 (tau={opt_5x['optimal_threshold']:.0f})\n  Rec={opt_5x['optimal_recall']:.1%}, Prec={opt_5x['optimal_precision']:.1%}")
    ax.annotate(f"Cost-Optimal 5:1 (tau={opt_5x['optimal_threshold']:.0f})\n(Rec={opt_5x['optimal_recall']:.1%}, Prec={opt_5x['optimal_precision']:.1%})",
                xy=(opt_5x['optimal_recall'], opt_5x['optimal_precision']),
                xytext=(opt_5x['optimal_recall'] - 0.32, opt_5x['optimal_precision'] - 0.16),
                arrowprops=dict(facecolor='#2ca02c', shrink=0.08, width=1.5, headwidth=8),
                fontweight='bold', color='#196F3D', bbox=dict(boxstyle='round,pad=0.3', fc='#e8f8f5', ec='#2ca02c', lw=1.2))

    # 3. Pragmatic Intermediate Point (tau = 380)
    row_380 = sweep_df.iloc[(sweep_df['threshold'] - 380.0).abs().argmin()]
    ax.scatter(row_380['recall'], row_380['precision'], color='#ff7f0e', s=120, zorder=5,
               edgecolor='black', linewidth=1.2,
               label=f"Pragmatic (tau=380)\n  Rec={row_380['recall']:.1%}, Prec={row_380['precision']:.1%}")

    ax.set_title("24-Hour Horizon Severe AQI (>=401) Precision-Recall Curve\nFixed CPCB Breakpoint vs. Cost-Aware Optimal Thresholds", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Recall (Severe Exceedance Detection Rate / Sensitivity)", fontweight='bold')
    ax.set_ylabel("Precision (Positive Predictive Value)", fontweight='bold')
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0.35, 1.02)
    ax.legend(loc='lower left', frameon=True, fontsize=10, shadow=True)

    plt.tight_layout()
    fig_path = 'reports/classification/figures/01_precision_recall_curve_24h.png'
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved: {fig_path}")


def plot_expected_cost_vs_threshold(sweep_df: pd.DataFrame,
                                    opt_summary: pd.DataFrame,
                                    cpcb_row: pd.Series):
    """Plot 2: Expected Cost Curves across Thresholds for Multiple Cost Ratios."""
    fig, ax = plt.subplots(figsize=(11, 7), dpi=300)

    palette = {
        1.0: ('#9467bd', '1:1 (Symmetric Cost)'),
        2.0: ('#17becf', '2:1 (Moderate Health Priority)'),
        3.0: ('#e377c2', '3:1 (High Health Priority)'),
        5.0: ('#2ca02c', '5:1 (Baseline Health Priority: C_FN = 5x C_FP)'),
        10.0: ('#d62728', '10:1 (Emergency Acute Crisis Priority)')
    }

    for r, (color, label) in palette.items():
        col = f'cost_rate_{int(r)}x'
        ax.plot(sweep_df['threshold'], sweep_df[col], color=color, linewidth=2.2, label=label)

        # Mark minimum
        opt_r = opt_summary[opt_summary['ratio_val'] == r].iloc[0]
        ax.scatter(opt_r['optimal_threshold'], opt_r['optimal_cost_rate'],
                   color=color, s=90, zorder=5, edgecolor='black')

    # Vertical line at fixed CPCB breakpoint (tau = 401)
    ax.axvline(401.0, color='#d62728', linestyle='--', linewidth=2.0,
               label='Statutory CPCB Breakpoint (tau = 401.0 AQI)')

    # Annotate the 5:1 optimum vs 401
    opt_5x = opt_summary[opt_summary['ratio_val'] == 5.0].iloc[0]
    ax.annotate(f"Optimal tau = {opt_5x['optimal_threshold']:.0f} AQI\nMin Cost = {opt_5x['optimal_cost_rate']:.3f}\n(-62.8% vs CPCB 401)",
                xy=(opt_5x['optimal_threshold'], opt_5x['optimal_cost_rate']),
                xytext=(opt_5x['optimal_threshold'] - 65, opt_5x['optimal_cost_rate'] + 0.65),
                arrowprops=dict(facecolor='#2ca02c', shrink=0.08, width=1.5, headwidth=7),
                fontweight='bold', color='#196F3D',
                bbox=dict(boxstyle='round,pad=0.3', fc='#e8f8f5', ec='#2ca02c', lw=1.2))

    ax.annotate(f"Fixed CPCB tau = 401\nCost (5:1) = {cpcb_row['cost_rate_5x']:.3f}",
                xy=(401.0, cpcb_row['cost_rate_5x']),
                xytext=(412.0, cpcb_row['cost_rate_5x'] + 0.45),
                arrowprops=dict(facecolor='#d62728', shrink=0.08, width=1.5, headwidth=7),
                fontweight='bold', color='#900C3F',
                bbox=dict(boxstyle='round,pad=0.3', fc='#ffe6e6', ec='#d62728', lw=1.2))

    ax.set_title("Expected Rate Cost vs. Severe Decision Threshold (tau)\nFormula: Expected Cost = FPR * 1.0 + FNR * (Cost Ratio)",
                 fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Severe Classification Decision Threshold tau (Predicted AQI)", fontweight='bold')
    ax.set_ylabel("Expected Rate Cost per Sample Opportunity", fontweight='bold')
    ax.set_xlim(260, 470)
    ax.set_ylim(0.2, 4.5)
    ax.legend(loc='upper right', frameon=True, fontsize=10, shadow=True)

    plt.tight_layout()
    fig_path = 'reports/classification/figures/02_expected_cost_vs_threshold.png'
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved: {fig_path}")


def plot_tradeoff_metrics(sweep_df: pd.DataFrame, cpcb_row: pd.Series):
    """Plot 3: Four-Panel Trade-off Metrics as a function of Threshold tau."""
    fig, axs = plt.subplots(2, 2, figsize=(14, 10), dpi=300)

    # Panel 1: Precision vs Recall vs F1
    axs[0, 0].plot(sweep_df['threshold'], sweep_df['recall'] * 100, color='#2ca02c', linewidth=2.5, label='Recall (Severe Sensitivity %)')
    axs[0, 0].plot(sweep_df['threshold'], sweep_df['precision'] * 100, color='#1f77b4', linewidth=2.5, label='Precision (PPV %)')
    axs[0, 0].plot(sweep_df['threshold'], sweep_df['f1'] * 100, color='#9467bd', linewidth=2.0, linestyle='-.', label='Severe F1-Score %')
    axs[0, 0].axvline(401.0, color='#d62728', linestyle='--', linewidth=1.5, label='CPCB 401 Breakpoint')
    axs[0, 0].axvline(341.0, color='#2ca02c', linestyle=':', linewidth=1.8, label='Cost-Optimal 5:1 (341)')
    axs[0, 0].set_title("(A) Precision, Recall & F1 Trade-off", fontweight='bold')
    axs[0, 0].set_xlabel("Decision Threshold tau (AQI)")
    axs[0, 0].set_ylabel("Percentage (%)")
    axs[0, 0].set_xlim(280, 460)
    axs[0, 0].set_ylim(40, 102)
    axs[0, 0].legend(loc='lower left', fontsize=9)

    # Panel 2: Error Rates (FPR vs FNR)
    axs[0, 1].plot(sweep_df['threshold'], sweep_df['fpr'] * 100, color='#ff7f0e', linewidth=2.5, label='False Alarm Rate (FPR %)')
    axs[0, 1].plot(sweep_df['threshold'], sweep_df['fnr'] * 100, color='#d62728', linewidth=2.5, label='Missed Hazardous Rate (FNR %)')
    axs[0, 1].axvline(401.0, color='#d62728', linestyle='--', linewidth=1.5)
    axs[0, 1].axvline(341.0, color='#2ca02c', linestyle=':', linewidth=1.8)
    axs[0, 1].set_title("(B) Error Rates: False Alarm vs. Missed Crisis", fontweight='bold')
    axs[0, 1].set_xlabel("Decision Threshold tau (AQI)")
    axs[0, 1].set_ylabel("Error Rate (%)")
    axs[0, 1].set_xlim(280, 460)
    axs[0, 1].set_ylim(-2, 85)
    axs[0, 1].legend(loc='upper center', fontsize=9)

    # Panel 3: Absolute Event Counts (Caught vs Missed)
    axs[1, 0].plot(sweep_df['threshold'], sweep_df['tp'], color='#2ca02c', linewidth=2.5, label='True Positives (Caught Severe Hours)')
    axs[1, 0].plot(sweep_df['threshold'], sweep_df['fn'], color='#d62728', linewidth=2.5, label='False Negatives (Missed Severe Hours)')
    axs[1, 0].axhline(4029, color='gray', linestyle=':', label='Total Actual Severe (4,029 h)')
    axs[1, 0].axvline(401.0, color='#d62728', linestyle='--', linewidth=1.5)
    axs[1, 0].axvline(341.0, color='#2ca02c', linestyle=':', linewidth=1.8)
    axs[1, 0].set_title("(C) Severe Event Catch vs. Miss Counts (Total = 4,029 h)", fontweight='bold')
    axs[1, 0].set_xlabel("Decision Threshold tau (AQI)")
    axs[1, 0].set_ylabel("Total Hours")
    axs[1, 0].set_xlim(280, 460)
    axs[1, 0].legend(loc='center left', fontsize=9)

    # Panel 4: False Alarm Count & Operational Load
    axs[1, 1].plot(sweep_df['threshold'], sweep_df['fp'], color='#ff7f0e', linewidth=2.5, label='False Alarms (FP Hours)')
    axs[1, 1].axvline(401.0, color='#d62728', linestyle='--', linewidth=1.5)
    axs[1, 1].axvline(341.0, color='#2ca02c', linestyle=':', linewidth=1.8)
    axs[1, 1].set_title("(D) False Alarm Operational Load (Total Non-Severe = 5,771 h)", fontweight='bold')
    axs[1, 1].set_xlabel("Decision Threshold tau (AQI)")
    axs[1, 1].set_ylabel("False Alarm Hours")
    axs[1, 1].set_xlim(280, 460)
    axs[1, 1].legend(loc='upper right', fontsize=9)

    plt.suptitle("24-Hour Horizon Multi-Metric Trade-off Suite across Decision Thresholds", fontsize=15, fontweight='bold', y=0.99)
    plt.tight_layout()
    fig_path = 'reports/classification/figures/03_tradeoff_metrics_vs_threshold.png'
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved: {fig_path}")


def plot_false_positive_composition(sweep_df: pd.DataFrame):
    """Plot 4: Composition of False Alarms across Underlying CPCB Categories."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    sub_df = sweep_df[(sweep_df['threshold'] >= 280) & (sweep_df['threshold'] <= 440)].copy()

    ax.plot(sub_df['threshold'], sub_df['fp_actual_vpoor'], color='#d95f02', linewidth=2.5,
            label='Actual Very Poor (301–400 AQI) [GRAP Stage II]')
    ax.plot(sub_df['threshold'], sub_df['fp_actual_poor'], color='#7570b3', linewidth=2.2,
            label='Actual Poor (201–300 AQI) [GRAP Stage I]')
    ax.plot(sub_df['threshold'], sub_df['fp_actual_mod_better'], color='#1b9e77', linewidth=2.0,
            label='Actual Moderate or Better (<=200 AQI) [Zero GRAP]')

    ax.axvline(401.0, color='#d62728', linestyle='--', linewidth=1.8, label='CPCB 401 Breakpoint')
    ax.axvline(341.0, color='#2ca02c', linestyle=':', linewidth=1.8, label='Cost-Optimal 5:1 (341)')

    ax.set_title("Anatomy of False Alarms: What Air Quality Was Actually Present?\nDemonstrating that False Alarms are Overwhelmingly Very Poor (GRAP Stage II) Air",
                 fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel("Decision Threshold tau (AQI)", fontweight='bold')
    ax.set_ylabel("False Alarm Hours (Count)", fontweight='bold')
    ax.set_xlim(280, 440)
    ax.legend(loc='upper right', frameon=True, fontsize=10, shadow=True)

    plt.tight_layout()
    fig_path = 'reports/classification/figures/04_false_positive_composition.png'
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved: {fig_path}")


def export_operating_points_comparison(sweep_df: pd.DataFrame):
    """Export a dedicated table comparing standard operating thresholds."""
    points = [401.0, 390.0, 380.0, 360.0, 341.0, 324.0, 300.0]
    rows = []

    for pt in points:
        idx = (sweep_df['threshold'] - pt).abs().argmin()
        r = sweep_df.iloc[idx]
        rows.append({
            'threshold_aqi': r['threshold'],
            'severe_recall_pct': r['recall'] * 100,
            'severe_precision_pct': r['precision'] * 100,
            'severe_f1_pct': r['f1'] * 100,
            'false_alarm_rate_fpr_pct': r['fpr'] * 100,
            'missed_rate_fnr_pct': r['fnr'] * 100,
            'true_severe_caught_h': int(r['tp']),
            'severe_missed_h': int(r['fn']),
            'false_alarms_total_h': int(r['fp']),
            'false_alarms_actual_vpoor_h': int(r['fp_actual_vpoor']),
            'false_alarms_actual_poor_h': int(r['fp_actual_poor']),
            'false_alarms_actual_mod_better_h': int(r['fp_actual_mod_better']),
            'cost_rate_1x': r['cost_rate_1x'],
            'cost_rate_5x': r['cost_rate_5x'],
            'cost_rate_10x': r['cost_rate_10x'],
            'sample_cost_5x': r['cost_sample_5x']
        })

    comp_df = pd.DataFrame(rows)
    comp_df.to_csv('reports/classification/metrics/threshold_operating_points_comparison.csv', index=False)
    print("Saved: reports/classification/metrics/threshold_operating_points_comparison.csv")
    return comp_df


def main():
    print("================================================================================")
    print("Executing Cost-Aware Risk Classification & Threshold Optimization (24h Horizon)")
    print("================================================================================")

    df_24h = load_data()
    print(f"Loaded 24h predictions: {df_24h.shape[0]} rows.")

    sweep_df, n_pos, n_neg, total_n = run_threshold_sweep(df_24h)
    sweep_df.to_csv('reports/classification/metrics/cost_threshold_sweep_24h.csv', index=False)
    print("Saved: reports/classification/metrics/cost_threshold_sweep_24h.csv")

    opt_summary, cpcb_row = find_cost_optimal_thresholds(sweep_df)
    opt_summary.to_csv('reports/classification/metrics/cost_optimal_thresholds_summary.csv', index=False)
    print("Saved: reports/classification/metrics/cost_optimal_thresholds_summary.csv")

    comp_df = export_operating_points_comparison(sweep_df)

    # Generate Plots
    plot_precision_recall_curve(sweep_df, df_24h, cpcb_row, opt_summary)
    plot_expected_cost_vs_threshold(sweep_df, opt_summary, cpcb_row)
    plot_tradeoff_metrics(sweep_df, cpcb_row)
    plot_false_positive_composition(sweep_df)

    print("\n=== Key Cost-Optimal Results ===")
    print(opt_summary[['cost_ratio_fn_to_fp', 'optimal_threshold', 'optimal_recall', 'optimal_precision', 'optimal_cost_rate', 'cost_rate_reduction_pct']])

    print("\n=== Operating Points Comparison ===")
    print(comp_df[['threshold_aqi', 'severe_recall_pct', 'severe_precision_pct', 'true_severe_caught_h', 'severe_missed_h', 'false_alarms_total_h', 'cost_rate_5x']])

    print("\nAll cost-aware classification artifacts generated successfully!")


if __name__ == '__main__':
    main()

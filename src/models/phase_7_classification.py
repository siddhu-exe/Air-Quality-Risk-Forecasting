import os
import pandas as pd
import numpy as np
import itertools
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score, average_precision_score

# ==============================================================================
# 1. Deterministic Binning Functions
# ==============================================================================

CPCB_BOUNDARIES = np.array([0, 51, 101, 201, 301, 401, 501])
CPCB_LABELS = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor', 'Severe']

def cpcb_classify(aqi_values: np.ndarray) -> np.ndarray:
    """Map continuous AQI to 0-5 CPCB ordinal classes."""
    # digitize gives us [0, 51)->1, [51, 101)->2, ..., [401, 501)->6
    # Subtract 1 to get 0-5 (0=Good, 1=Satis, 2=Mod, 3=Poor, 4=V.Poor, 5=Severe)
    classes = np.digitize(aqi_values, CPCB_BOUNDARIES[1:-1], right=False)
    # Clip just in case there are negative numbers or highly out of bounds positives
    return np.clip(classes, 0, 5)

def grap_stage_from_aqi(aqi_values: np.ndarray) -> np.ndarray:
    """
    Map continuous AQI to GRAP stages:
    0 = No stage (<= 200)
    1 = Stage I (201-300)
    2 = Stage II (301-400)
    3 = Stage III (401-450)
    4 = Stage IV (>450)
    """
    stages = np.zeros_like(aqi_values, dtype=np.int8)
    stages[aqi_values >= 201] = 1
    stages[aqi_values >= 301] = 2
    stages[aqi_values >= 401] = 3
    stages[aqi_values > 450] = 4
    return stages

def compute_ordinal_mae(y_true_class, y_pred_class):
    return np.mean(np.abs(y_true_class - y_pred_class))

def compute_weighted_kappa(y_true_class, y_pred_class, k=6):
    cm = confusion_matrix(y_true_class, y_pred_class, labels=np.arange(k))
    n = np.sum(cm)
    if n == 0:
        return np.nan

    p_o = cm / n
    p_e = np.outer(np.sum(p_o, axis=1), np.sum(p_o, axis=0))

    # Quadratic weights
    w = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            w[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)

    num = np.sum(w * p_o)
    den = np.sum(w * p_e)

    # Handle perfect agreement / edge cases
    if den == 0:
        return 1.0 if num == 0 else 0.0

    return 1 - (num / den)

# ==============================================================================
# 2. Episode Logic
# ==============================================================================

def detect_episodes(df: pd.DataFrame, threshold: float, col_name: str, max_gap: int = 3):
    """
    Detect episodes where actual AQI >= threshold.
    Episodes separated by <= max_gap hours are merged.
    Works per station.
    """
    episodes = []

    for station_id, group in df.groupby('station_id'):
        group = group.sort_values('timestamp').reset_index()

        # Binary flag for exceedance
        is_exceeding = group[col_name] >= threshold

        # Connect gaps <= max_gap
        # 1. We dilate the exceedance mask by max_gap/2 in both directions roughly,
        # or more simply, we find run lengths of 0s, and if length <= max_gap, we flip them to 1.

        # Let's do a simple iterative approach since N is small per station (max ~1400 rows)
        exceed_arr = is_exceeding.values.copy()

        i = 0
        n = len(exceed_arr)
        while i < n:
            if not exceed_arr[i] and i > 0 and i < n - 1:
                # We are in a gap. Check how big it is.
                gap_start = i
                while i < n and not exceed_arr[i]:
                    i += 1
                gap_end = i
                gap_len = gap_end - gap_start

                # If bounded by 1s (i.e. not at the very end of series) and gap <= max_gap
                if gap_len <= max_gap and i < n and exceed_arr[gap_start - 1] and exceed_arr[i]:
                    exceed_arr[gap_start:gap_end] = True
            else:
                i += 1

        # Now extract contiguous groups of True
        in_episode = False
        start_idx = -1

        for i in range(n):
            if exceed_arr[i] and not in_episode:
                in_episode = True
                start_idx = i
            elif not exceed_arr[i] and in_episode:
                in_episode = False
                end_idx = i - 1

                # Record episode
                ep_data = group.iloc[start_idx:end_idx+1]
                episodes.append({
                    'station_id': station_id,
                    'station_name': group['station_name'].iloc[0],
                    'start_time': ep_data['timestamp'].min(),
                    'end_time': ep_data['timestamp'].max(),
                    'peak_aqi': ep_data[col_name].max(),
                    'duration_hours': (ep_data['timestamp'].max() - ep_data['timestamp'].min()).total_seconds() / 3600 + 1,
                    # We need the exact original threshold crossing for evaluation, not the smoothed one
                    'first_actual_crossing': ep_data[ep_data[col_name] >= threshold]['timestamp'].min()
                })

        # Handle episode at end of series
        if in_episode:
            end_idx = n - 1
            ep_data = group.iloc[start_idx:end_idx+1]
            episodes.append({
                'station_id': station_id,
                'station_name': group['station_name'].iloc[0],
                'start_time': ep_data['timestamp'].min(),
                'end_time': ep_data['timestamp'].max(),
                'peak_aqi': ep_data[col_name].max(),
                'duration_hours': (ep_data['timestamp'].max() - ep_data['timestamp'].min()).total_seconds() / 3600 + 1,
                'first_actual_crossing': ep_data[ep_data[col_name] >= threshold]['timestamp'].min()
            })

    return pd.DataFrame(episodes)

def analyze_horizon(df: pd.DataFrame, horizon: str, actual_col: str, pred_col: str):
    """Run all classification & evaluation logic for a single horizon."""
    print(f"=== Analyzing {horizon} Horizon ===")
    
    # ----------------------------------------------------
    # Multi-class CPCB Evaluation
    # ----------------------------------------------------
    df = df.copy().dropna(subset=[actual_col, pred_col])
    
    y_true_cpcb = cpcb_classify(df[actual_col].values)
    y_pred_cpcb = cpcb_classify(df[pred_col].values)
    
    df['category_actual'] = y_true_cpcb
    df['category_predicted'] = y_pred_cpcb
    df['category_name_actual'] = [CPCB_LABELS[i] for i in y_true_cpcb]
    df['category_name_predicted'] = [CPCB_LABELS[i] for i in y_pred_cpcb]
    
    df['is_correct'] = y_true_cpcb == y_pred_cpcb
    df['ordinal_error'] = y_pred_cpcb - y_true_cpcb
    df['abs_ordinal_error'] = np.abs(df['ordinal_error'])
    
    df['severe_actual'] = df[actual_col] >= 401
    df['severe_predicted'] = df[pred_col] >= 401
    
    df['vpoor_plus_actual'] = df[actual_col] >= 301
    df['vpoor_plus_predicted'] = df[pred_col] >= 301
    
    # GRAP logic
    df['grap_stage_actual'] = grap_stage_from_aqi(df[actual_col].values)
    df['grap_stage_forecast'] = grap_stage_from_aqi(df[pred_col].values)
    df['stage_iii_alert'] = df[pred_col] >= 401
    df['stage_iv_alert'] = df[pred_col] > 450
    df['any_grap_alert'] = df[pred_col] >= 201
    
    # Export row-level classified data
    df.to_parquet(f"reports/classification/{horizon}/classified_predictions.parquet", index=False)
    
    # Metrics computation
    # Macro F1, Weighted F1
    macro_f1 = f1_score(y_true_cpcb, y_pred_cpcb, average='macro')
    weighted_f1 = f1_score(y_true_cpcb, y_pred_cpcb, average='weighted')
    
    macro_prec = precision_score(y_true_cpcb, y_pred_cpcb, average='macro', zero_division=0)
    macro_rec = recall_score(y_true_cpcb, y_pred_cpcb, average='macro', zero_division=0)
    
    w_kappa = compute_weighted_kappa(y_true_cpcb, y_pred_cpcb)
    ord_mae = compute_ordinal_mae(y_true_cpcb, y_pred_cpcb)
    
    # Class-specific (Severe is 5)
    labels = np.unique(np.concatenate([y_true_cpcb, y_pred_cpcb]))
    severe_mask = (y_true_cpcb == 5)
    
    if 5 in labels:
        severe_f1 = f1_score(y_true_cpcb, y_pred_cpcb, labels=[5], average='macro')
        severe_rec = recall_score(y_true_cpcb, y_pred_cpcb, labels=[5], average='macro', zero_division=0)
        severe_prec = precision_score(y_true_cpcb, y_pred_cpcb, labels=[5], average='macro', zero_division=0)
    else:
        severe_f1, severe_rec, severe_prec = np.nan, np.nan, np.nan
        
    vpoor_plus_rec = recall_score(y_true_cpcb >= 4, y_pred_cpcb >= 4)
    
    # Critical Miss Rate (Actual Severe predicted as <= Moderate (<=2))
    total_actual_severe = np.sum(severe_mask)
    if total_actual_severe > 0:
        critical_misses = np.sum((y_true_cpcb == 5) & (y_pred_cpcb <= 2))
        critical_miss_rate = critical_misses / total_actual_severe
    else:
        critical_miss_rate = np.nan
        
    metrics = {
        'horizon': horizon,
        'macro_f1': macro_f1,
        'weighted_f1': weighted_f1,
        'macro_precision': macro_prec,
        'macro_recall': macro_rec,
        'weighted_kappa': w_kappa,
        'ordinal_mae': ord_mae,
        'severe_f1': severe_f1,
        'severe_recall': severe_rec,
        'severe_precision': severe_prec,
        'vpoor_plus_recall': vpoor_plus_rec,
        'critical_miss_rate': critical_miss_rate
    }
    
    # Confusion matrix
    cm = confusion_matrix(y_true_cpcb, y_pred_cpcb, labels=np.arange(6))
    cm_df = pd.DataFrame(cm, index=[f"True_{L}" for L in CPCB_LABELS], columns=[f"Pred_{L}" for L in CPCB_LABELS])
    cm_df.to_csv(f"reports/classification/metrics/confusion_matrix_{horizon}.csv")
    
    return metrics, df

def process_all():
    print("Loading 1h predictions...")
    p1 = pd.read_parquet('data/Artifacts/1h/predictions_1h_test.parquet')
    
    print("Loading 6h predictions...")
    p6 = pd.read_parquet('data/Artifacts/6h/predictions_6h_test.parquet')
    
    print("Loading 24h predictions...")
    p24 = pd.read_parquet('reports/modeling/24h/final/final_predictions.parquet')
    
    metrics_list = []
    
    m1, df1 = analyze_horizon(p1, '1h', 'y_true', 'y_pred')
    metrics_list.append(m1)
    
    m6, df6 = analyze_horizon(p6, '6h', 'y_true', 'y_pred')
    metrics_list.append(m6)
    
    m24, df24 = analyze_horizon(p24, '24h', 'target_aqi_24h', 'prediction_hybrid_6c_winning')
    metrics_list.append(m24)
    
    metrics_df = pd.DataFrame(metrics_list)
    metrics_df.to_csv('reports/classification/metrics/multiclass_metrics_comparison.csv', index=False)
    print("\nMetrics comparison saved to reports/classification/metrics/multiclass_metrics_comparison.csv")
    print(metrics_df[['horizon', 'macro_f1', 'severe_recall', 'ordinal_mae']])
    
    # ----------------------------------------------------
    # binary severe detection & Episode Lead Time Logic
    # ----------------------------------------------------
    # For episode detection, we will look at Severe episodes (AQI >= 401)
    # in the 24h actuals as a base source of truth since all horizons share the same period natively.
    # Actually, we should evaluate lead time per horizon.
    
    episodes_all = []
    
    for h, df, actual_col, pred_col in [('1h', df1, 'y_true', 'y_pred'),
                                        ('6h', df6, 'y_true', 'y_pred'),
                                        ('24h', df24, 'target_aqi_24h', 'prediction_hybrid_6c_winning')]:
        
        # Binary severe thresholds for AUPRC/AUROC estimation
        try:
            auroc_300 = roc_auc_score(df[actual_col] >= 300, df[pred_col])
            auroc_400 = roc_auc_score(df[actual_col] >= 401, df[pred_col])
            auprc_400 = average_precision_score(df[actual_col] >= 401, df[pred_col])
        except Exception as e:
            auroc_300 = np.nan
            auroc_400 = np.nan
            auprc_400 = np.nan
            
        print(f"[{h}] AUROC >= 401: {auroc_400:.4f}, AUPRC >= 401: {auprc_400:.4f}")
        
        # Episode detection for Stage III (>=401)
        eps = detect_episodes(df, 401.0, actual_col, max_gap=3)
        if len(eps) > 0:
            eps['horizon'] = h
            
            # For each episode, determine Lead Time
            lead_times = []
            hit_miss = []
            for _, ep in eps.iterrows():
                # We filter predictions made AT OR BEFORE the first actual occurrence.
                # Actually, the 'timestamp' in these dfs is the issuance time of the forecast.
                # For 24h, a forecast issued at T predicts T+24.
                # If ep['first_actual_crossing'] is T_actual, any forecast issued at T <= T_actual
                # that predicts >=401 is an early warning. 
                # Let's align on the time spaces.
                # In these files, `timestamp` might be issuance time or target time depending on how it was saved.
                # Let's assume `timestamp` = target time for comparability, because phase_5 logic: 
                # 'target_aqi_24h' is literally AQI at target time. 
                # So the forecast was issued at `timestamp - horizon`.
                
                if h == '1h': h_td = pd.Timedelta(hours=1)
                elif h == '6h': h_td = pd.Timedelta(hours=6)
                else: h_td = pd.Timedelta(hours=24)
                
                # issuance_time = df['timestamp'] - h_td
                
                # To find lead time: 
                # Did we predict the crossover beforehand?
                # The prediction for T_cross is made at T_cross - h_td
                # So if at T_cross - h_td we predicted that T_cross will be >= 401, we have h_td lead time!
                # If we predicted it even earlier (for an earlier point in the episode), we have more lead time relative to episode start.
                
                # Let's find all predictions made BEFORE T_actual that predicted >=401 for ANY time within the episode.
                episode_actual_start = ep['first_actual_crossing']
                episode_actual_end = ep['end_time']

                station_df = df[df['station_id'] == ep['station_id']]

                # We need forecasts that PREDICT >=401 that FALL within the episode time window or slightly before.
                # Actually, an alert is valid for an episode if the predicted target time falls within the episode [+ a small operational window, say 24h before]
                # GRAP alerting: "If ANY forecast in the next 72h indicates Severe".
                # For our simplified evaluation: Did a forecast issued BEFORE episode_actual_start predict >=401 for a target time between [episode_actual_start, episode_actual_end]?

                severe_preds = station_df[(station_df[pred_col] >= 401)]
                severe_preds = severe_preds.copy()
                severe_preds['issuance_time'] = severe_preds['timestamp'] - h_td

                # Condition 1: Target time is within the actual episode (meaning it accurately predicted this specific event)
                # Or at least within 12 hours of the start
                valid_alerts = severe_preds[
                    (severe_preds['timestamp'] >= episode_actual_start - pd.Timedelta(hours=12)) &
                    (severe_preds['timestamp'] <= episode_actual_end)
                ]

                # Condition 2: Issued BEFORE or AT the actual crossing
                valid_alerts = valid_alerts[valid_alerts['issuance_time'] <= episode_actual_start]

                if len(valid_alerts) > 0:
                    first_alert_time = valid_alerts['issuance_time'].min()

                    lt = (episode_actual_start - first_alert_time).total_seconds() / 3600
                    # cap lead time realistically; a forecast 24h ahead cannot give 30h lead time. Max lead time should be bounded by horizon.
                    # Since we only look at horizon H, the maximum possible lead time for a perfect forecast exactly H hours ahead of start is H.
                    # If it predicted an exceedance at target time T_target (which is after T_start), and was issued at T_target - H <= T_start,
                    # the lead time is T_start - (T_target - H) = H - (T_target - T_start).
                    # Max lead time is H.
                    status = 'hit'
                else:
                    lt = 0
                    status = 'miss'
                    
                lead_times.append(lt)
                hit_miss.append(status)
                
            eps['lead_time_hours'] = lead_times
            eps['detection'] = hit_miss
            episodes_all.append(eps)
            
    if len(episodes_all) > 0:
        all_eps_df = pd.concat(episodes_all, ignore_index=True)
        all_eps_df.to_csv('reports/classification/episodes/grap_episode_lead_times.csv', index=False)
        
        print("\nEpisode Detection Summary (>=401):")
        sum_df = all_eps_df.groupby(['horizon', 'detection']).size().unstack(fill_value=0)
        print(sum_df)
        print("\nMean Lead Time (Hits only):")
        hits = all_eps_df[all_eps_df['detection'] == 'hit']
        if len(hits) > 0:
            print(hits.groupby('horizon')['lead_time_hours'].mean())

if __name__ == '__main__':
    process_all()

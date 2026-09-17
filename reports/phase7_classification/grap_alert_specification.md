# Phase 7 GRAP Alert Specification

**Document Version:** 1.0  
**Status:** DRAFT — Design & Specification Phase  
**Date:** 2026-09-16  
**Depends On:** `reports/phase7_classification/target_definition.md`, `reports/phase7_classification/risk_classification_specification.md`

---

## 1. Purpose

This document specifies the **GRAP (Graded Response Action Plan) Stage I–IV alerting logic** for Phase 7. The system generates early-warning alerts from **forecasted AQI values** (not observed AQI) to simulate the CAQM's 2024 revised proactive invocation framework.

**Key Principle:** GRAP alerts are **forecast-derived**, enabling lead-time measurement. Actual AQI is used only for evaluation (hit/miss/false alarm/lead time).

---

## 2. GRAP Stages — Official 2024 Revised Definitions

**Authority:** Commission for Air Quality Management (CAQM), Delhi-NCR  
**Legal Basis:** Commission for Air Quality Management in National Capital Region and Adjoining Areas Act, 2021  
**2024 Revision:** Proactive/forecast-based invocation + sustained revocation

| GRAP Stage | Category Label | AQI Range | Key Actions (Summary) |
|---|---|---|---|
| **Stage I** | Poor | 201 – 300 | Waste burning ban, dust control, mechanized sweeping, PUC enforcement |
| **Stage II** | Very Poor | 301 – 400 | Enhanced parking fees, diesel generator restrictions, increased transit, water sprinkling |
| **Stage III** | Severe | 401 – 450 | Construction ban, BS-III/BS-IV vehicle restrictions, school hybrid mode, brick kiln closure |
| **Stage IV** | Severe+ | > 450 | Truck entry ban, all construction halt, school closures, WFH advisory, possible odd-even |

---

## 3. Critical Distinction: CPCB Categories vs GRAP Stages

| Aspect | CPCB AQI Categories | GRAP Stages |
|---|---|---|
| **Purpose** | Health risk communication | Emergency regulatory enforcement |
| **Scope** | All India | Delhi-NCR only |
| **Tiers** | 6 (0–500) | 4 (aligned to Poor/VP/Severe/Severe+) |
| **Severe Boundary** | Single: 401–500 | **Split: 401–450 (Stage III) and >450 (Stage IV)** |
| **Invocation** | Instantaneous (daily AQI) | **Forecast-based (up to 3 days advance)** |
| **Revocation** | N/A | **Sustained: 2–3 days below threshold + forecast confirmation** |
| **Legal Force** | Advisory | **Enforceable orders with penalties** |

**⚠️ DO NOT CONFLATE:** CPCB "Severe" (401–500) ≠ GRAP "Severe" (Stage III: 401–450). GRAP splits CPCB's Severe into two operationally distinct emergency tiers.

---

## 4. Alert Generation Logic

### 4.1 Deterministic Stage Mapping (Forecast-Based)

```python
def grap_stage_from_forecast(aqi_forecast: float) -> int:
    """
    Map forecasted AQI to GRAP stage.
    
    Returns:
        0 = No stage (AQI ≤ 200)
        1 = Stage I (201–300)
        2 = Stage II (301–400)
        3 = Stage III (401–450)
        4 = Stage IV (>450)
    """
    if aqi_forecast > 450:
        return 4  # Stage IV
    elif aqi_forecast >= 401:
        return 3  # Stage III
    elif aqi_forecast >= 301:
        return 2  # Stage II
    elif aqi_forecast >= 201:
        return 1  # Stage I
    else:
        return 0  # No GRAP stage (Good/Satisfactory/Moderate)
```

### 4.2 Proactive Invocation (2024 Revision)

**Rule:** A GRAP stage may be invoked **up to 3 days (72 hours) in advance** if the forecast trajectory indicates the AQI threshold will be crossed.

**Operationalization for Phase 7:**
- For each forecast horizon $h \in \{1\text{h}, 6\text{h}, 24\text{h}\}$, we compute the **maximum forecasted stage** across the horizon window
- For 24h horizon: if any forecast in the next 24h indicates Stage III/IV, alert is issued at $t$
- Lead time = (timestamp of forecast threshold crossing) - (timestamp of actual threshold crossing)

### 4.3 Sustained Revocation Logic (Evaluation Only)

For episode evaluation (not real-time alerting), we simulate the 2024 revocation rule:

```python
def is_stage_sustained(forecast_series: np.ndarray, stage: int, 
                       min_days: int = 2) -> bool:
    """
    Check if forecast sustains a GRAP stage for minimum consecutive days.
    Used for revocation evaluation in episode analysis.
    """
    # Stage thresholds
    thresholds = {1: 201, 2: 301, 3: 401, 4: 451}
    threshold = thresholds[stage]
    
    # Count consecutive hours above threshold
    above = forecast_series >= threshold
    # Convert to days (24h periods)
    # Simplified: require 48-72 consecutive hours
    max_consecutive = max(len(list(g)) for v, g in itertools.groupby(above) if v)
    return max_consecutive >= min_days * 24
```

---

## 5. Alert Targets for Evaluation

### 5.1 Primary Alert Targets (Per Horizon)

| Target | Definition | Evaluation Use |
|--------|------------|----------------|
| **Stage III Alert** | $\mathbb{1}[\max_{h' \le h} \hat{y}^{(h')} \ge 401]$ | Early warning for Severe episode |
| **Stage IV Alert** | $\mathbb{1}[\max_{h' \le h} \hat{y}^{(h')} > 450]$ | Early warning for Severe+ episode |
| **Stage Escalation Alert** | $\mathbb{1}[\text{stage}(t+h) > \text{stage}(t)]$ | Trend detection |

### 5.2 Binary Alert Targets (Aligned with Classification)

| Binary Target | Forecast Condition | Actual Condition (Ground Truth) |
|---|---|---|
| **Stage III+ Alert** | $\hat{y}^{(h)} \ge 401$ | $y_{true}^{(h)} \ge 401$ |
| **Stage IV Alert** | $\hat{y}^{(h)} > 450$ | $y_{true}^{(h)} > 450$ |
| **Any GRAP Alert** | $\hat{y}^{(h)} \ge 201$ | $y_{true}^{(h)} \ge 201$ |

---

## 6. Episode-Based Detection Framework

### 6.1 Episode Definition

An **episode** is a contiguous period where actual AQI exceeds a threshold:

| Episode Type | Threshold | Minimum Duration |
|---|---|---|
| **Poor Episode** | AQI ≥ 201 | 1 hour |
| **Very Poor Episode** | AQI ≥ 301 | 1 hour |
| **Severe Episode** | AQI ≥ 401 | 1 hour |
| **Severe+ Episode** | AQI > 450 | 1 hour |

**Episode Merging:** Gap ≤ 3 hours between exceedances → same episode.

### 6.2 Episode Detection Metrics

For each episode in the test set (Nov–Dec 2025):

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Hit (True Positive)** | Alert issued ≥ 1h before episode start | Correct early warning |
| **Miss (False Negative)** | No alert before episode start | Failed to warn |
| **False Alarm (False Positive)** | Alert issued, no episode within 24h | Unnecessary alarm |
| **Correct Rejection (True Negative)** | No alert, no episode | Correct silence |
| **Lead Time** | $t_{alert} - t_{episode\_start}$ | Hours of advance warning (negative = late) |
| **Detection Latency** | $t_{first\_alert} - t_{episode\_start}$ | Time to first alert after episode begins |

### 6.3 Episode-Level Evaluation Table

| Episode ID | Type | Start Time | End Time | Peak AQI | Duration (h) | Alert Issued? | Lead Time (h) | Hit/Miss/FA |
|---|---|---|---|---|---|---|---|---|
| EP_2025_001 | Severe (≥401) | 2025-11-05 06:00 | 2025-11-07 14:00 | 432 | 56 | Yes (24h) | +18.5 | Hit |
| EP_2025_002 | Severe+ (>450) | 2025-11-12 18:00 | 2025-11-13 08:00 | 467 | 14 | Yes (6h) | +4.0 | Hit |
| EP_2025_003 | Severe (≥401) | 2025-12-01 04:00 | 2025-12-02 02:00 | 418 | 22 | No | N/A | Miss |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

---

## 7. Lead-Time Evaluation Methodology

### 7.1 Lead Time Definition

**Lead Time = Forecast Threshold Crossing Time - Actual Threshold Crossing Time**

- **Positive lead time:** Alert issued before actual crossing (early warning) → **GOOD**
- **Zero lead time:** Alert coincides with actual crossing → **BASELINE**
- **Negative lead time:** Alert issued after actual crossing → **LATE**

### 7.2 Lead Time Computation (Per Horizon)

For each horizon $h$ and each severe episode:

```python
def compute_lead_time(forecast_series: np.ndarray, 
                      actual_series: np.ndarray,
                      threshold: float,
                      timestamps: pd.DatetimeIndex) -> dict:
    """
    forecast_series: model predictions at horizon h for each timestep
    actual_series: observed AQI at horizon h for each timestep
    threshold: 401 (Stage III) or 451 (Stage IV)
    """
    # Find first forecast crossing
    forecast_cross_idx = np.where(forecast_series >= threshold)[0]
    actual_cross_idx = np.where(actual_series >= threshold)[0]
    
    if len(forecast_cross_idx) == 0 or len(actual_cross_idx) == 0:
        return {'lead_time_hours': None, 'status': 'no_crossing'}
    
    t_forecast = timestamps[forecast_cross_idx[0]]
    t_actual = timestamps[actual_cross_idx[0]]
    
    lead_hours = (t_forecast - t_actual).total_seconds() / 3600
    
    if lead_hours > 0:
        status = 'early_warning'
    elif lead_hours == 0:
        status = 'coincident'
    else:
        status = 'late'
    
    return {
        'lead_time_hours': lead_hours,
        'status': status,
        'forecast_cross_time': t_forecast,
        'actual_cross_time': t_actual
    }
```

### 7.3 Lead Time Aggregation

| Aggregation | Description |
|---|---|
| **Mean Lead Time** | Average hours of advance warning across episodes |
| **Median Lead Time** | Robust central tendency |
| **Lead Time Distribution** | Histogram / percentiles (P10, P50, P90) |
| **Early Warning Rate** | Fraction of episodes with lead time > 0 |
| **Actionable Lead Time** | Fraction with lead time ≥ 6h (operational relevance) |

---

## 8. Per-Horizon Alert Specification

### 8.1 1-Hour Horizon Alerts
- **Use Case:** Imminent risk confirmation, real-time operations
- **Lead Time Expectation:** 0–1 hours (mostly coincident)
- **Primary Value:** Confirming episode onset, triggering immediate response

### 8.2 6-Hour Horizon Alerts
- **Use Case:** Intra-day planning (morning→afternoon, afternoon→evening)
- **Lead Time Expectation:** 0–6 hours
- **Primary Value:** Operational adjustments (traffic, construction, school decisions)

### 8.3 24-Hour Horizon Alerts
- **Use Case:** Next-day planning, GRAP policy pre-positioning
- **Lead Time Expectation:** Up to 24 hours (per 2024 revision: up to 72h)
- **Primary Value:** Proactive GRAP invocation, resource mobilization, public advisory

---

## 9. Alert Output Schema

### 9.1 Per-Row Alert Results (Parquet)

| Column | Type | Description |
|---|---|---|
| `station_id` | int64 | Station identifier |
| `station_name` | string | Station name |
| `timestamp` | datetime64[ns, UTC] | Forecast issuance time |
| `horizon` | string | '1h' \| '6h' \| '24h' |
| `aqi_forecast` | float64 | Phase 6 prediction at horizon |
| `grap_stage_forecast` | int8 | 0–4 (forecast-derived) |
| `grap_stage_actual` | int8 | 0–4 (observed AQI-derived, for evaluation) |
| `stage_iii_alert` | bool | Forecast ≥ 401 |
| `stage_iv_alert` | bool | Forecast > 450 |
| `any_grap_alert` | bool | Forecast ≥ 201 |
| `lead_time_iii_hours` | float32 | Lead time for Stage III (if episode) |
| `lead_time_iv_hours` | float32 | Lead time for Stage IV (if episode) |
| `episode_id` | string | Episode identifier (if in episode) |
| `hit_miss_fa` | string | 'hit' \| 'miss' \| 'false_alarm' \| 'correct_rejection' |

### 9.2 Episode Summary (CSV)

| Column | Type | Description |
|---|---|---|
| `episode_id` | string | Unique episode identifier |
| `episode_type` | string | 'Poor' \| 'Very Poor' \| 'Severe' \| 'Severe+' |
| `start_time` | datetime | Episode onset |
| `end_time` | datetime | Episode end |
| `peak_aqi` | float64 | Maximum AQI during episode |
| `duration_hours` | float32 | Episode duration |
| `alert_1h` | bool | 1h horizon alert issued |
| `alert_6h` | bool | 6h horizon alert issued |
| `alert_24h` | bool | 24h horizon alert issued |
| `lead_time_1h` | float32 | 1h lead time (hours) |
| `lead_time_6h` | float32 | 6h lead time (hours) |
| `lead_time_24h` | float32 | 24h lead time (hours) |
| `detection_1h` | string | hit/miss/false_alarm |
| `detection_6h` | string | hit/miss/false_alarm |
| `detection_24h` | string | hit/miss/false_alarm |

---

## 10. Alert Evaluation Metrics

### 10.1 Binary Alert Metrics (Per Horizon, Per Stage)

| Metric | Formula |
|---|---|
| **Alert Precision** | $\frac{TP}{TP + FP}$ |
| **Alert Recall (Sensitivity)** | $\frac{TP}{TP + FN}$ |
| **Alert F1** | $2 \cdot \frac{\text{Prec} \cdot \text{Rec}}{\text{Prec} + \text{Rec}}$ |
| **False Alarm Rate** | $\frac{FP}{FP + TN}$ |
| **Specificity** | $\frac{TN}{FP + TN}$ |
| **AUROC** | Area under ROC curve (varying forecast threshold) |
| **AUPRC** | Area under Precision-Recall curve |

### 10.2 Episode-Level Metrics

| Metric | Formula |
|---|---|
| **Episode Hit Rate** | $\frac{\text{Episodes with alert before start}}{\text{Total episodes}}$ |
| **Mean Lead Time (Hit Episodes)** | $\frac{1}{N_{hit}}\sum \text{lead\_time}_i$ |
| **Median Lead Time** | $\text{median}(\text{lead\_time}_i \text{ for hits})$ |
| **Actionable Warning Rate** | $\frac{\text{Episodes with lead\_time} \ge 6\text{h}}{\text{Total episodes}}$ |
| **Missed Episode Rate** | $\frac{\text{Episodes with no alert}}{\text{Total episodes}}$ |

### 10.3 Multi-Horizon Comparative Metrics

| Comparison | Purpose |
|---|---|
| Hit Rate: 1h vs 6h vs 24h | Does longer horizon catch more episodes early? |
| Lead Time: 1h vs 6h vs 24h | Trade-off: earlier warning vs lower precision |
| False Alarm Rate: 1h vs 6h vs 24h | Cost of early warning |
| Stage III vs Stage IV Detection | Is Severe+ easier/harder to detect than Severe? |

---

## 11. Leakage Controls (Alert-Specific)

| Control | Implementation |
|---|---|
| **No threshold optimization** | GRAP thresholds fixed by regulation (201, 301, 401, 451) |
| **Forecast-only for alerts** | Actual AQI never used to generate alerts |
| **No hysteresis tuning** | Sustained duration rules fixed (2–3 days per 2024 revision) |
| **Test set only for evaluation** | All metrics computed on frozen Nov–Dec 2025 split |
| **No alert calibration** | Raw forecast → stage mapping; no Platt scaling |

---

## 12. Visualization Requirements

| Plot | Purpose |
|---|---|
| Lead time distribution by horizon (boxplot) | Compare early warning capability |
| Episode timeline: actual AQI + forecast + alert markers | Qualitative validation |
| Hit/Miss/FA rates by horizon (grouped bar) | Operational trade-off visualization |
| ROC curves for Stage III/IV alerts (per horizon) | Threshold sensitivity analysis |
| Lead time vs episode peak AQI (scatter) | Does lead time depend on severity? |
| GRAP stage transition diagram | Alert escalation patterns |

---

## 13. Acceptance Criteria

- [ ] Deterministic GRAP stage mapping from forecast AQI (fixed thresholds)
- [ ] Proactive invocation logic: max forecast stage over horizon window
- [ ] Episode detection with merging (≤3h gap)
- [ ] Lead time computation: forecast crossing vs actual crossing
- [ ] Binary alert metrics: Precision, Recall, F1, AUROC, AUPRC for Stage III/IV
- [ ] Episode-level metrics: Hit Rate, Mean/Median Lead Time, Actionable Warning Rate
- [ ] Per-row alert results saved as Parquet
- [ ] Episode summary saved as CSV
- [ ] Multi-horizon comparison tables generated
- [ ] Zero leakage: fixed thresholds, no test-set tuning, forecast-only alerts

---

**Next Document:** `reports/phase7_classification/evaluation_strategy.md` — Unified evaluation framework combining classification metrics, binary severe-event detection, episode detection, lead-time analysis, and cross-horizon synthesis.
# Delhi Air Quality Risk Forecasting → Portfolio Site: Hand-off Guide (for an LLM / developer)

Everything needed to update **Delhi Air Quality Risk Forecasting** on the Siddharth Dongardive portfolio site
(`/home/siddharth/Desktop/Projects/projects/Portfolio`) lives in this folder. Same layout as `LegalRAG/portfolio/`.
Follow the site's own guides: `Portfolio/docs/ADDING_PROJECTS.md`, `Portfolio/docs/CHAPTER_PAGE.md`,
`Portfolio/docs/PROJECT_GUIDE.md`.

Files here: `images/` (all visuals, §5), `scripts/generate_portfolio_images.py` (regenerates the drawn figures
`10`–`51` from files in `reports/` and `data/`), and `AIR_QUALITY_PORTFOLIO.md` (the long case-study spec).

> **Source of truth.** Every number below comes from `reports/metrics/headline_metrics.csv`
> (`src/evaluation/build_metrics_table.py`), `reports/classification/metrics/`, `reports/classification/episodes/`,
> `reports/causal/regression_models_summary.csv`, `reports/modeling/live_audit/`. If this guide and those files
> disagree, the files win. Last refreshed 2026-10-14.

---

## 1. Steps to update the project (summary)

1. Copy the images (§5.2) into `Portfolio/frontend/public/images/delhi-air-quality-risk-forecasting/`.
2. Update `Portfolio/frontend/src/data/projects/delhi-air-quality-risk-forecasting.js` (the filled model is
   `legalrag.js`): copy, stats, stack, chapters, figures (§3).
3. Update `Portfolio/backend/data.py` (`"Delhi Air Quality Risk Forecasting"` entry: `result`, `thumbnail`,
   `heroImage`, `gallery_overrides`) and mirror it in `frontend/src/data/fallbackProjects.js`.
4. Restart the backend, open the shelf, click the book, then **View Full Project**; check every gallery section
   (1 image = full width, 2 = side by side, 3+ = scroll row).

Slug: `delhi-air-quality-risk-forecasting`. Image folder name must match the slug.

---

## 2. Project facts (single source of truth for copy)

| Field | Value |
|---|---|
| Name | Delhi Air Quality Risk Forecasting |
| One-liner | 1h / 6h / 24h AQI forecasts for 7 Delhi stations, cost-sensitive CPCB/GRAP alerting, and a causal test of the Diwali firecracker ban, all scored against naive persistence. |
| Role framing | **ML Engineer / Data Scientist** (data engineering, modeling, causal inference, dashboards). |
| GitHub | https://github.com/siddhu-exe/Air-Quality-Risk-Forecasting |
| Demo | Streamlit (legacy): https://siddhu-exe-air-quality-risk-forecasting-dashboardapp-w5wwow.streamlit.app/ |
| Dataset | https://www.kaggle.com/datasets/siddharthdongardive/delhi-air-quality-monitoring-dataset-2023-2026 (220,042 hourly rows) |
| Demo caveat | Both dashboards **replay pre-computed backtest files**. They are not a live feed. The new React dashboard currently runs on **sample data** and shows a "Sample readings · live feed pending" badge. |
| Year | 2026 |
| Data | 105 CPCB/DPCC source files, 7 CAAQMS stations, hourly, 2023–2026; 162,096 telemetry rows in PostgreSQL 16 |
| Features | 124 leakage-safe features (lags, rolling, seasonal, weather, spatial) with a written leakage audit |
| Splits (Asia/Kolkata) | Train Jan–Aug 2025 · Validation Sep–Oct 2025 · **Test Nov–Dec 2025** (scored once, 24h embargo) |

### Tech stack (keep to ~8–10 chips)
`Python`, `PostgreSQL 16`, `LightGBM`, `scikit-learn (Ridge)`, `Statsmodels`, `FastAPI`, `React + TypeScript`,
`Streamlit`, `Plotly`, `GitHub Actions`. Others if room: `Vite`, `Tailwind CSS`, `Supabase`, `pytest`, `Open-Meteo`.

### How it works (7 stages)
1. **Raw data** — 105 CPCB/DPCC spreadsheets, 7 stations.
2. **ETL + QC** — header/unit mapping, sentinel values nulled per cell, QC flags kept as JSONB.
3. **PostgreSQL 16** — idempotent upserts with source-file lineage.
4. **Features** — 124 backward-looking features; 2023–24 AQI recomputed from raw telemetry by the CPCB method.
5. **Forecasts** — LightGBM for 1h/6h; 50/50 Persistence + Ridge hybrid (α = 1000) for 24h.
6. **Decisions** — CPCB categories, GRAP stages I–IV, alert cutoffs chosen on validation only.
7. **Serving** — FastAPI + React dashboard (and legacy Streamlit) reading files in `reports/`.

### Engineering highlights (true, defensible)
- **Persistence-first evaluation.** AQI is a 24h rolling average (lag-1 r ≈ 0.998), so "copy the last value" is a very
  strong baseline. Every result is reported with skill = 1 − metric_model / metric_persistence and 95% day-block
  bootstrap CIs. At 1h the model does **not** beat persistence on RMSE (−0.332); that is reported, not hidden.
- **Diagnosed the extrapolation wall.** 24h gradient-boosted trees scored MAE 98.24 because trees cannot predict above
  the training AQI max (~347) and calendar features sent winter rows into monsoon leaves. A Ridge + persistence hybrid
  gave MAE 34.11 (+11% skill), and the gain held in a second winter (+0.099 in 2024).
- **Found and removed a test-set leak** in alert-threshold selection (an earlier "95.7% recall" is retired).
- **Honest causal analysis.** Naive before/after says +135.6 AQI; a +20.4 pts/day pre-trend and a significant placebo
  (+24.3) invalidate it; ITS gives −10.6 (p = 0.51). The ban effect is **not identifiable** (it was active every year).
- **Tier 2 experiments that did not move the headline** (more winters, weather, PM2.5 target, quantile intervals,
  max-compute tuning) are documented rather than hidden. None replace the frozen models.
- **Tier 3 live-pipeline groundwork (stages 1–3):** Supabase schema + roles with RLS, hourly ingest, forecast job with
  parity checks, and a feature-availability audit. The audit re-scores the frozen 24h model on validation with the
  live feed's inputs (no NOx, weather swapped): skill +0.053 vs +0.055 baseline, so it survives. Live serving is **not** switched on
  (no fresh public source yet).

### Key results (use these exact numbers)

Forecasting, test winter Nov–Dec 2025 (`headline_metrics.csv`):

| Horizon | Model | MAE | Persistence MAE | MAE skill | RMSE skill | R² |
|---|---|---|---|---|---|---|
| 1h | Tuned LightGBM | 2.29 | 2.40 | +0.047 | **−0.332** | 0.992 |
| 6h | Tuned LightGBM | 11.84 | 12.72 | +0.069 | +0.091 | 0.919 |
| 24h | 50/50 Persistence + Ridge | 34.11 | 38.34 | **+0.110** | +0.117 | 0.365 |
| 24h | Same, +2024 winters in training | 34.02 | 38.34 | +0.113 | +0.120 | 0.368 |

Alerting, 24h, Severe = AQI ≥ 401 (test winter, 41% of hours are Severe; validation only 2.4%):

| Policy | Cutoff | Severe recall | Severe precision | Missed / false-alarm hours |
|---|---|---|---|---|
| Statutory CPCB | 401 | 61.08% | 73.86% | 1,568 / 871 |
| Compromise | 380 | 78.90% | 64.40% | 850 / 1,757 |
| Validation-optimal (5:1 cost) | 274.5 | 99.83% | 42.93% | 7 / 5,347 |

At 274.5 persistence reaches 99.63% / 43.03%, so the model adds no skill there. Episode early warning (24h, 86
episodes): hit rate 69.8% vs 65.1% persistence, mean lead 10.5 h vs 7.7 h.

Causal (Diwali 2025, 7 stations, ±14 days, date-clustered SEs): naive +135.57; ITS −10.59 (p = 0.51); placebo +24.26.
Festival-night PM2.5 peak 960.7 µg/m³ (8.0× baseline), SO₂ tracer 5.3×, dispersing in ~18–24 h.

Tier 2: PM2.5 target beats persistence at 1h (+0.20) and 6h (+0.37), not 24h (−0.09). Conformal 80% intervals cover
76% (target 80%). Max-compute tuning did not beat the standard run on test.

---

## 3. Ready-to-paste data

### 3.1 `data.py` entry
```python
"Delhi Air Quality Risk Forecasting": {
    "subtitle": "Forecasts, alerts and a causal test, all scored against persistence.",
    "sort_order": 2, "tag": "ML", "published": True,
    "result": "+11% 24h skill vs persistence · MAE 98.24 → 34.11",
    "spineColor": "#2F4A3A",
    "thumbnail": "/images/delhi-air-quality-risk-forecasting/40_dashboard_overview.png",
    "heroImage": "/images/delhi-air-quality-risk-forecasting/10_architecture.png",
    # description / links unchanged
    "gallery_overrides": { ... },   # see §5.3
},
```
The old `result` line ("0.000% critical misses · 95.71% 24h severe recall") is **retired**: the 95.7% recall came from a
test-set-selected threshold, and "zero critical misses" is trivial on a smoothed target.

### 3.2 Stats (4 tiles)
`162,096` telemetry rows · `124` leakage-safe features · `+11%` 24h skill vs persistence · `p = 0.51` Diwali ITS shift.

### 3.3 Section copy for the gallery subtitles

| key | Heading | Suggested subtitle |
|---|---|---|
| architecture | Architecture | From raw government spreadsheets to risk alerts: one pipeline, every stage leaves files the next one reads. |
| pipeline | Data Pipeline | The relational model, and the time splits that keep the test winter untouched. |
| ml | Machine Learning | Skill against persistence, the 24h extrapolation fix, and a real episode forecast. |
| platform | Platform | The Delhi Air Forecast dashboard: overview, stations, operations and model health. |
| results | Results | What alerts cost, and why the Diwali ban effect cannot be identified. |

---

## 4. Highlights (three bullets if the site needs them)
- Idempotent PostgreSQL 16 ETL over 105 CPCB/DPCC files; 124 leakage-safe features with a written audit.
- 1h/6h LightGBM and a 24h Ridge + persistence hybrid, all reported against persistence with bootstrap CIs.
- Cost-sensitive GRAP alert thresholds chosen on validation only, plus ITS/placebo causal analysis showing the Diwali-ban effect is not identifiable.

---

## 5. Images — which one goes where

All files are in `portfolio/images/`. Drawn figures (10–51) use the site's tokens (cream / ink / terracotta, Playfair
Display + Inter) and are regenerated with `./venv/bin/python portfolio/scripts/generate_portfolio_images.py`.
Frame ratios: 1 image = 16:9, 2 images = 4:3 each, 3+ = scroll row.

### 5.1 Image catalogue

| File | Size | What it shows |
|---|---|---|
| `10_architecture.png` | 3200×1800 | 7-stage pipeline: raw data → ETL → Postgres → features → forecasts → decisions → serving, plus the causal question and evaluation rules |
| `20_data_model.png` | 2400×1800 | Relational model (stations, telemetry, official AQI, lineage) |
| `21_splits_timeline.png` | 2400×1800 | Train / validation / test windows and the 24h embargo |
| `30_skill_vs_persistence.png` | 2400×1800 | MAE skill vs persistence at 1h / 6h / 24h |
| `31_extrapolation_fix.png` | 2400×1800 | Trees capped at ~347 vs the Ridge + persistence hybrid (MAE 98.24 → 34.11) |
| `32_episode_forecast.png` | 2400×1800 | A real Severe episode: forecast vs actual vs persistence |
| `40_dashboard_overview.png` | 1440×900 | **New React dashboard** — tomorrow's city AQI, 80% range, advice, station map (sample data) |
| `41_dashboard_stations.png` | 1440×900 | Stations page |
| `42_dashboard_operations.png` | 1440×900 | Operations page (GRAP stage view) |
| `43_dashboard_model_health.png` | 1440×900 | Model health: skill vs copy-last, coverage, Brier, data freshness |
| `44_streamlit_legacy_forecasts.png` | 2400×1800 | Original Streamlit forecast tab (legacy) |
| `50_alert_tradeoff.png` | 2400×1800 | Precision–recall of Severe alerts, three operating points, vs persistence |
| `51_diwali_identification.png` | 2400×1800 | Why naive Diwali before/after fails: pre-trend, placebo, ITS |
| `01`–`07`, `diwali_timeline_pretrends`, `precision_recall_curve_24h`, `tradeoff_metrics_vs_threshold` | various | **Older images** (Sep 2025). Superseded; `03`/`05`/`07` are still acceptable fallbacks. Do not use `06`'s "95.7%" framing in copy. |

The React screenshots show the **sample-data** badge on purpose; keep the caption "sample readings, live feed pending".
Re-capture after Tier 3 stage 5 when the dashboard reads the real API.

### 5.2 Where each is used

| Site slot | Image(s) | Reason |
|---|---|---|
| `thumbnail` / book-preview modal | `40_dashboard_overview.png` | Most recognisable single view |
| Gallery `architecture` (1, 16:9) | `10_architecture.png` | System overview |
| Gallery `pipeline` (2) | `20_data_model.png`, `21_splits_timeline.png` | Data model + leakage-safe splits |
| Gallery `ml` (3, scroll row) | `30_skill_vs_persistence.png`, `31_extrapolation_fix.png`, `32_episode_forecast.png` | Skill, the failure + fix, a real episode |
| Gallery `platform` (2) | `40_dashboard_overview.png`, `43_dashboard_model_health.png` | The interface and its honesty page |
| Gallery `results` (2) | `50_alert_tradeoff.png`, `51_diwali_identification.png` | Alerting trade-off + causal finding |
| Spare | `41`, `42`, `44` | Add to `platform` to make a scroll row |

### 5.3 `gallery_overrides`
```python
"gallery_overrides": {
    "architecture": ["/images/delhi-air-quality-risk-forecasting/10_architecture.png"],
    "pipeline": [".../20_data_model.png", ".../21_splits_timeline.png"],
    "ml": [".../30_skill_vs_persistence.png", ".../31_extrapolation_fix.png", ".../32_episode_forecast.png"],
    "platform": [".../40_dashboard_overview.png", ".../43_dashboard_model_health.png"],
    "results": [".../50_alert_tradeoff.png", ".../51_diwali_identification.png"],
},
```
(prefix every `...` with `/images/delhi-air-quality-risk-forecasting`.)

Copy command (from this repo root):
```bash
D=/home/siddharth/Desktop/Projects/projects/Portfolio/frontend/public/images/delhi-air-quality-risk-forecasting
mkdir -p $D && cp portfolio/images/{10,20,21,30,31,32,40,41,42,43,44,50,51}_*.png $D/
```

---

## 6. Claims to avoid

- ❌ "95.7% / 95.71% severe recall" or "0.000% critical misses" — test-set-selected threshold / trivial on a smoothed target.
- ❌ "Live" / "real-time" forecasts — dashboards replay backtest files; the React app is on sample data.
- ❌ "Beats persistence at 1h" — it wins on MAE (+0.047) but loses on RMSE (−0.332). Say "no real 1h skill".
- ❌ "Diwali ban reduced (or did not reduce) pollution" — say "not identifiable with this data".
- ❌ Stubble burning / boundary-layer height as established causes — they are hypotheses; the project has no fire or PBLH data in the headline analysis.
- ❌ "Tier 3 live pipeline deployed" — stages 1–3 are built; live serving is off until a fresh source is confirmed.
- ⚠️ Say "backtest on one held-out winter (Nov–Dec 2025)". Validation has 2.4% Severe hours vs 41% in test, so alert cutoffs shift between seasons.
- ⚠️ 24h R² is 0.365 — the gain is a modest, honest +11% MAE skill, not a high-accuracy 24h forecast.

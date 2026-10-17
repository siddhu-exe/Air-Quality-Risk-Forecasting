# Resume material

Numbers are from `reports/modeling/live_retrain/` and `reports/live/` (test winter 2025-11-01..12-31, scored once; 95%
day-block bootstrap intervals).

## Bullets

1. Diagnosed train/serve skew in a live Delhi AQI forecasting service (trained on official AQI, served on recomputed AQI); retraining on the served definition lifted 6h skill vs persistence from −0.05 to +0.30 (95% CI +0.24 to +0.35).
2. Benchmarked LightGBM against persistence and a parameter-free 24h-window-update rule: the rule won at 1h (+0.55 vs +0.34 skill), the model at 6h (+0.30), so production serves each where it is best.
3. Built and deployed hourly forecasts for 7 Delhi stations: GitHub Actions ingest/forecast/scoring, Supabase Postgres, FastAPI on Azure Container Apps, React on Vercel, with hash-pinned models, parity tests and a shadow-mode gate for an unreliable upstream source.

## LinkedIn project summary

Hourly air-quality forecasts for 7 Delhi stations, every result scored against copy-the-last-value with confidence intervals, on a live pipeline (GitHub Actions, Supabase, FastAPI, React).
Found and fixed train/serve skew (6h skill −0.05 to +0.30), showed a simple rule beats ML at 1h, and handled dead data sources with a probe, a shadow feed and a pre-registered gate.

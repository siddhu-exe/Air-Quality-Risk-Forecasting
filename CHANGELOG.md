# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Dates are when the work landed on `main`. Metrics are not quoted here; see `reports/metrics/headline_metrics.md`.

## [Unreleased] - Tier 3 (live pipeline)

### Added
- Live pipeline: source adapters, QC, AQI recompute, forecast job and parity check (`src/live/`), Supabase schema (`db/migrations/`), manual GitHub Actions workflows.
- WAQI round-trip audit, station check and calibration side check (`reports/modeling/live_audit/`, `docs/TIER_3/`).
- Live-consistent retrain: AQI 1h/6h/24h, PM2.5 and quantile models in `models/live/` with sha256 in `config/live_model_hashes.json` (`docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md`).
- React frontend (`frontend/`), running on sample data until the API exists.
- `LICENSE` (MIT), `pyproject.toml` (ruff, pytest), `Makefile`, pre-commit hooks, CI, `docs/ARCHITECTURE.md`, decision records.

### Changed
- Frozen-model D1 skill numbers are corrected for the recomputed-AQI basis (`docs/TIER_3/PLAN.md`).
- Internal phase notes removed from `docs/`; plan history moved to `docs/history/`.
- Diwali analysis reads database settings from the environment instead of source code.

### Fixed
- `requirements-forecast.txt` pins `pyarrow` (the unpinned release needs numpy 2).

## Tier 2 - honest evaluation

Recomputed 2024 AQI target, rolling-origin backtest, extended 24h training, raw PM2.5 forecast, exogenous driver ablation, quantile and conformal intervals (`docs/TIER_2/`).

## Tier 1 - defects fixed

Single headline-metrics table, validation-selected alert thresholds, a fixed episode lead-time metric, a reframed causal analysis, a real test suite and repo hygiene (`docs/history/TIER_1_IMPROVEMENTS.md`).

## Phases 1 to 8 - research pipeline

ETL into PostgreSQL, EDA, 124-feature leakage-safe matrix, LightGBM 1h/6h, Ridge+persistence 24h, CPCB/GRAP classification with cost-aware thresholds, Diwali causal analysis, Streamlit dashboard and Kaggle dataset export.

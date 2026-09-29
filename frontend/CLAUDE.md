# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Context

This is the **React + Vite frontend** for the Delhi Air Quality Risk Forecasting system — migrating from an existing Streamlit dashboard (`../dashboard/app.py`) to a production-grade single-page application. The app visualises multi-horizon AQI forecasts (1h / 6h / 24h), CPCB/GRAP regulatory alerts, econometric Diwali policy analysis, and cost-sensitive threshold exploration across 7 Delhi monitoring stations.

The design system is fully specified in `stitch_air_quality_intelligence_dashboard/precision_atmospheric_analytics/DESIGN.md` and the three reference HTML prototypes in the same directory. **All styling decisions must follow those specs** — do not deviate on colour, typography, or spacing without a written reason.

---

## Commands

```bash
# Install dependencies
npm install

# Development server (Vite HMR)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint

# Run a single test file
npm test -- src/components/AQICard.test.tsx
```

---

## Architecture

### Tech Stack
- **Framework:** React 18 + Vite
- **Language:** TypeScript
- **Styling:** Tailwind CSS (config mirrors the Precision Atmospheric Analytics design tokens — see `tailwind.config.ts`)
- **Charts:** Recharts (preferred) or Plotly.js for complex geo/time-series views
- **State:** Zustand for global state (horizon selector, active station, GRAP alert state)
- **Routing:** React Router v6 — single shell with tab-based section switching (no full page reload)
- **Data fetching:** React Query (`@tanstack/react-query`) with a mock data layer while a live API is unavailable
- **Fonts:** `Inter` (prose/labels) + `JetBrains Mono` (metrics/telemetry values) loaded via Google Fonts

### Design Tokens
The canonical token set lives in `DESIGN.md` and is compiled into `tailwind.config.ts`. Custom classes follow the naming convention from the prototype HTML files:
- `font-label-code` / `text-label-code` — monospaced telemetry values
- `text-metric-display` — large KPI numerics
- `font-label-caps` / `text-label-caps` — uppercase section headers with `0.06em` tracking
- Surface hierarchy: `surface-container-lowest` → `surface-container-low` → `surface-container` → `surface-container-high` → `surface-container-highest`
- AQI tier colours: `#10B981` Good · `#F59E0B` Moderate · `#F97316` Poor · `#F43F5E` Very Poor · `#A855F7` Severe

### Directory Layout (target structure)
```
src/
├── components/          # Shared UI primitives (KPICard, AQIBadge, DataTable, AlertBanner…)
├── features/
│   ├── forecasts/       # Multi-horizon forecast view (1h / 6h / 24h)
│   ├── causal/          # Diwali ITS econometric view
│   ├── thresholds/      # Cost-aware threshold simulator
│   ├── stations/        # Station diagnostic explorer
│   └── overview/        # Live KPI strip + GRAP status
├── hooks/               # Custom React hooks (useHorizon, useStation, useAlerts…)
├── store/               # Zustand slices
├── data/                # Static JSON/CSV proxies and mock generators
│   └── mock/            # Mirrors ../reports/classification/ and ../reports/causal/ CSVs
├── lib/                 # Utility functions (AQI tier mapping, GRAP stage logic, formatters)
├── types/               # Shared TypeScript interfaces (AQIReading, Forecast, Station…)
└── assets/
```

### Data Layer
While a live API does not exist, the frontend loads static data mirroring the real backend outputs:

| Report file (backend) | Frontend proxy location |
|---|---|
| `reports/classification/{1h,6h,24h}/classified_predictions.parquet` | `src/data/mock/predictions_{1,6,24}h.json` |
| `reports/causal/diwali_hourly_timeseries.csv` | `src/data/mock/diwali_hourly.json` |
| `reports/causal/regression_models_summary.csv` | `src/data/mock/diwali_regression.json` |
| `reports/classification/metrics/cost_threshold_sweep_24h.csv` | `src/data/mock/threshold_sweep.json` |
| `reports/classification/episodes/grap_episode_lead_times.csv` | `src/data/mock/episodes.json` |

All data-fetching hooks live in `src/data/` and expose a uniform `{ data, isLoading, error }` shape so they can be swapped for real API calls later.

### Key Business Logic (in `src/lib/`)
- `aqi.ts` — CPCB 6-tier classification (Good 0–50, Satisfactory 51–100, Moderate 101–200, Poor 201–300, Very Poor 301–400, Severe 401+) and GRAP Stage I–IV mapping
- `thresholds.ts` — asymmetric 5:1 loss ratio optimisation; cost-optimal cutoff is **341.5 AQI** (do not hard-code elsewhere)
- `formatters.ts` — ISO 8601 → `Asia/Kolkata` display formatting using `date-fns-tz`

### Navigation / Sections
Mirrors the Streamlit 5-tab layout:
1. **Real-Time & Forecasts** — KPI bento strip, per-station AQI, horizon selector (1h/6h/24h), GRAP banner
2. **Model Performance** — forecast accuracy table, P-R curves, confusion matrices
3. **Causal Impact** — Diwali ITS charts, chemical tracer surge, placebo overlay
4. **Risk Threshold** — interactive cost-sweep slider, operating-point comparison
5. **Methodology** — static markdown renderer with schema diagram and audit tables

### Sidebar
Fixed left sidebar (`w-64`) shows live station telemetry list and GRAP mitigation status — always visible on ≥ 1280 px, collapses to a drawer on tablet/mobile.

---

## Reference Prototypes

Three fully-styled static HTML files exist in `stitch_air_quality_intelligence_dashboard/` and are the visual ground-truth:
- `delhi_air_quality_risk_forecasting_data_first/code.html` — main dashboard shell, KPI strip, station sidebar
- `diwali_causal_impact_lab_minimal/code.html` — causal analysis panel
- `model_performance_cost_optimization_minimal/code.html` — model metrics and threshold view

When building a new component, open the corresponding HTML prototype first and extract the exact Tailwind classes — do not redesign.

---

## Backend Integration Notes
- The Streamlit backend (`../dashboard/app.py`) reads from `../reports/` Parquet and CSV files; these same files are the source of truth for the mock data layer.
- Station IDs: `Anand Vihar`, `ITO`, `Punjabi Bagh`, `RK Puram`, `Mandir Marg`, `Dwarka`, `Okhla Phase 2`
- All timestamps are `Asia/Kolkata` (UTC+5:30); display in IST, store in UTC.
- Model artifacts live in `../models/`; they are not loaded by the frontend — only their pre-computed prediction CSVs are consumed.

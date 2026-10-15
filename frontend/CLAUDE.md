# CLAUDE.md

Guidance for working in `frontend/`. The repo-wide context is in `../CLAUDE.md`.

## What this is

The Delhi Air Forecast dashboard: four pages (Overview, Stations, Operations, Model health) that show the live AQI, the AQI and PM2.5 forecasts that exist for the CAAQMS stations (and why the others do not), an indicative GRAP outlook, and how the forecasts are doing against "copy-last-value" (persistence) and, for AQI, the 24h-window update rule. It is a React + Vite single-page app. It replaced the old dark "Precision Atmospheric" UI, the Diwali and threshold screens, Recharts and Zustand; do not bring them back.

What is published (ADR 0006, `../docs/decisions/0006-live-forecast-products.md`): AQI 1h is a **rule** ("Rule-based (24h-window update)"), AQI 6h is a model, AQI 24h is **experimental** ("about as accurate as assuming no change") and always shows plain persistence beside it, PM2.5 1h and 6h are models, **PM2.5 24h is withheld**. There is **no interval and no P(severe)**: neither is published, so no screen may draw one.

The design is the source of truth. It is archived in `../docs/design/`:

- `Delhi Air Forecast Dashboard.html` is the packed bundle.
- `pages/*.dc.html` are the readable page sources; open the matching one before changing a page.

Match the design's layout, tokens and tone. Where the design shows something the API no longer publishes (the 24h range, the chance of Severe, "tomorrow" as the headline), the API contract wins: the screen shows what exists.

## Commands

```bash
npm install
npm run dev          # Vite on http://localhost:3000, sample data by default
npm run build        # tsc --noEmit, then vite build
npm run type-check
npm run lint
npm test             # vitest run (jsdom)
npm test -- src/lib/chart.test.ts   # one file
```

Before calling work done, run `type-check`, `lint`, `test` and `build`. Run them one after another: the dev laptop is weak, so do not run them in parallel or alongside a dev server. The first visit to each lazy page is slow under jsdom, which is why `testTimeout` is 20 s and Testing Library's `asyncUtilTimeout` is 10 s.

## Stack

React 18, Vite 5, TypeScript (strict), Tailwind CSS v3.4, TanStack Query v5, React Router v7 (data router, lazy routes), zod, Radix Dialog (mobile menu), `tailwind-merge` + `clsx`. Tests: Vitest, Testing Library, jsdom. Fonts: Geist, Geist Mono, Instrument Serif. Charts are hand-built SVG; there is no chart library.

`@/` is an alias for `src/`.

## Layout

```
src/
  app/          App, providers, query client, router (routes.tsx), RootLayout, error/fallback screens
  api/          schemas.ts (zod contract), http.ts (real client), mock/ (sample client + fixtures),
                queries.ts (TanStack hooks), describeError.ts
  config/       env.ts (parsed VITE_* variables)
  design/       tokens.ts, the single source of truth for colour, type and spacing
  components/
    ui/         Card, Page, Skeleton, ErrorState, StaleBanner, SegmentedControl, Eyebrow
    aqi/        CategoryPill, AqiScaleBar, tierClasses.ts (AQI tier class maps)
    forecast/   ForecastCell: one forecast as a value or the reason there is none
    charts/     ForecastChart (+ ForecastPlot, SeriesTable), Sparkline, FreshnessStrip
    layout/     SiteHeader, SectionNav, MobileNav, StatusCluster, SkipLink, Logo
  features/     overview/, stations/, operations/, model-health/: one folder per page
  lib/          pure logic and formatting (aqi, advice, chart, forecast, format, ranking, skill, projection, cn)
  styles/       index.css (Tailwind layers, focus ring, reduced motion)
  test/         setup.ts, renderApp.tsx (renderAt(path) with the real routes and providers)
```

Put logic that can be a pure function in `lib/` and test it there. Components should mostly arrange data that `lib/` already shaped.

## Data layer

- The contract is `src/api/schemas.ts` (zod), mirroring the models in `../backend/app/models.py` (decision: `../docs/decisions/0008-api-contract.md`). `../backend/` is not part of frontend work; change the contract on both sides together.
- Every forecast is `ok` (a value, with plain `persistence` and, for AQI, `windowUpdate`), `unavailable` (with the `reason` the forecast job recorded) or `withheld`. Show the reason (`lib/forecast.ts` `reasonLabel` shortens it; keep the full text as the tooltip and sr-only text). **Never render a blank cell and never a substitute number.** A forecast job that is not running, a stale station, a dropped PM2.5 reading and a missing hourly AQI are all normal states: in the Sep-Oct 2026 replay only 65-74% of station-hours had a forecast.
- `VITE_USE_MOCK` defaults to `true`: pages are served by `api/mock/`, which runs the fixtures through the same schemas, so a fixture that drifts from the contract fails in tests. The fixture deliberately contains a stale station, a station with PM2.5 dropped and one with the 1h rule unavailable. Set `VITE_USE_MOCK=false` to call the real API at `VITE_API_BASE_URL` (default `/api/v1`, proxied by Vite to `http://localhost:8000`). Copy `.env.example` to `.env.local`.
- Pages read data only through the hooks in `api/queries.ts` (`useOverview`, `useStations`, `useStationForecast`, `useGrapAlerts`, `useModelHealth`, `useBacktest`, `useHealth`). Do not call `fetch` from components.
- Loading, error and stale are all handled: each page shows a skeleton, an `ErrorState` with "Try again", and a `StaleBanner` when the server says the data is stale or there are no readings (`dataAsOf` is null). Show ages against the server clock (`generatedAt`), not the browser's.
- All times are `Asia/Kolkata`. Format them with `lib/format.ts`; never call `toLocaleString` directly.
- City-level numbers on the Overview are computed in `lib/forecast.ts` (`outlook`) as the mean over the stations that have the forecast, and always say how many that is ("5 of 7 stations").

## Styling rules

- **No raw hex values or arbitrary colours in components.** Colours, type sizes and spacing come from `design/tokens.ts`, which feeds `tailwind.config.ts` and the SVG charts.
- Tailwind class names follow the nested token keys: `bg-grap-bg`, `border-grap-rule`, `bg-status-active-bg`, `text-fresh-late`, `bg-inverse` / `text-inverse-text`, `fill-map-land`. There is no `bg-grap`. When a class has no effect, check the token key before anything else.
- Type sizes are pixel-named (`text-13`, `text-17`, `text-136`). `lib/cn.ts` registers them with `tailwind-merge`; add any new size to that list too, or `text-13 text-ink-muted` will silently drop the size.
- AQI tier colours are literal class strings in `components/aqi/tierClasses.ts` so Tailwind can see them. Do not build class names with template strings.
- Responsive layout is one DOM tree with Tailwind classes (`hidden md:flex`, `md:hidden`). jsdom has no CSS, so tests see both variants: use `getAllBy…(…)[0]` or `within(...)`.
- Cards use `px-5 md:px-7`. The breakpoint for the phone layout is `md` (768 px); the Severe alerts table switches at `lg`.

## Accessibility rules

- Never use colour alone: status is also words (and sr-only text such as "(late)").
- Charts are `role="img"` with a generated description (`describeSeries`, which says "no forecast available" when there is none), and each has a "View as table" twin. The hover readout is for pointer users only and is `aria-hidden`.
- Tables are real `<table>`s with `th scope`. Scrollable regions are focusable (`tabIndex={0}`, with the lint rule disabled and a comment saying why).
- The map is `role="group"` with a generated label and per-pin links; a pin for a station with no reading is grey, one with an old reading is faded, and both say so in their label. Station pills are links with `aria-current`, inside a labelled `nav`.
- Focus ring is global (`:focus-visible` in `styles/index.css`). `prefers-reduced-motion` is handled globally in the same file; do not add motion that bypasses it.
- Interactive targets are at least 44 px (`min-h-target`) on touch layouts.

## Charts

`lib/chart.ts` holds the geometry and is pure and tested: viewBox 960 x 340, plot area x 56 to 936, y 10 to 300. Default domains are AQI 150 to 500 and PM2.5 50 to 450, widened in steps of 50 when data leaves them. The shaded zones start at AQI 300 and 400, and PM2.5 120 and 250. The forecast is a few **published points** (+1h, +6h, +24h; only the `ok` ones, from `lib/forecast.ts` `chartForecast`), drawn as a line from "now" through those points with a dot on each; there is no band because no range is published. With no forecast the chart still draws the history and a short empty future, and says so in its description. A station with no history draws no chart and says why. `buildChartModel` returns paths, ticks and per-hour `samples`; `nearestSample` drives the readout and `buildSeriesRows` feeds the table. Change the maths in `lib/chart.ts` and its test, not in the component.

## Copy and data honesty

- Copy that depends on data is generated from the data (`lib/forecast.ts`, `lib/ranking.ts`, the summary sentences). Do not hard-code numbers into sentences.
- Labels come from the API (`label`, `kind`, `experimental`); the UI adds the badge (`kindBadge`: Rule-based / Model / Experimental). The 24h AQI is always shown with "same as now"; the Operations table shows it beside its persistence.
- Skill is always reported against copy-last (`persistence`) and, for AQI 6h, against the 24h-window update; the evidence table (`/backtest`) carries the intervals and both windows (the Nov-Dec 2025 test and the Sep-Oct 2026 replay), including where the result is no better than assuming no change.
- GRAP stages are served by the API, labelled "indicative only, not an official advisory", and based on current readings and the 6h model. The drafted advice text for the AQI bands (`lib/advice.ts`, marked REVIEW BEFORE LAUNCH) is pending the project owner's review.

## Testing

- Pure logic: unit tests next to the file (`lib/*.test.ts`).
- Components and pages: Testing Library with `renderAt('/stations/bawana')` from `src/test/renderApp.tsx`, which uses the real routes, providers and mock client.
- `src/test/setup.ts` works around three jsdom gaps (React Router's `Request`, `scrollTo`, `PointerEvent`). Pointer tests need a stubbed `getBoundingClientRect` because there is no layout.

## Verifying visually

```bash
npx vite --port 3011 &        # note the PID and kill it by PID afterwards
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --virtual-time-budget=8000 --window-size=1440,1100 --screenshot=out.png http://localhost:3011/stations/bawana
```

Headless Chrome will not lay out narrower than about 500 px, so "phone" screenshots are really 500 px wide; check 390 px in browser dev tools. Never use `pkill -f` with a pattern that also appears in your own command line: it kills the shell.

## Deployment

`vercel.json` serves the static build with an SPA rewrite and immutable caching for `/assets/`. In the Vercel project set `VITE_API_BASE_URL` to the full API URL (`https://<container-app-fqdn>/api/v1`) and `VITE_USE_MOCK=false`; then set `FRONTEND_ORIGIN` on the Container App to the Vercel URL, or the browser will refuse the API's answers (CORS). Setup steps: `../docs/TIER_3/VERCEL_SETUP.md`.

## Status

Stage 6 (2026-10-15): schemas, fixtures, every page and `CLAUDE.md` rewritten to the API contract of ADR 0008. Not yet done: a visual pass against the design for the new states (no-forecast cells, empty chart), and the Vercel deployment. Update this section when that lands.

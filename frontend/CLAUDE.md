# CLAUDE.md

Guidance for working in `frontend/`. The repo-wide context is in `../CLAUDE.md`.

## What this is

The Delhi Air Forecast dashboard: four pages (Overview, Stations, Operations, Model health) that show hourly AQI and PM2.5 forecasts for the CAAQMS stations, the GRAP outlook, and how the models are doing against "copy-last-value" (persistence). It is a React + Vite single-page app. It replaced the old dark "Precision Atmospheric" UI, the Diwali and threshold screens, Recharts and Zustand; do not bring them back.

The design is the source of truth. It is archived in `../docs/design/`:

- `Delhi Air Forecast Dashboard.html` is the packed bundle.
- `pages/*.dc.html` are the readable page sources; open the matching one before changing a page.

Match the design. If the code and the design disagree, the design wins unless the user says otherwise.

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

Before calling work done, run `type-check`, `lint`, `test` and `build`. Run them one after another: the dev laptop is weak, so do not run them in parallel or alongside a dev server. The first visit to each lazy page is slow under jsdom, which is why `testTimeout` is 20 s and Testing Library's `asyncUtilTimeout` is 5 s.

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
    ui/         Card, Page, Skeleton, ErrorState, StaleBanner, SegmentedControl, ProgressBar, Eyebrow
    aqi/        CategoryPill, AqiScaleBar, tierClasses.ts (AQI tier class maps)
    charts/     ForecastChart (+ ForecastPlot, SeriesTable), Sparkline, RangeBar, FreshnessStrip
    layout/     SiteHeader, SectionNav, MobileNav, StatusCluster, SkipLink, Logo
  features/     overview/, stations/, operations/, model-health/: one folder per page
  lib/          pure logic and formatting (aqi, advice, chart, format, ranking, leadTime, skill, projection, cn)
  styles/       index.css (Tailwind layers, focus ring, reduced motion)
  test/         setup.ts, renderApp.tsx (renderAt(path) with the real routes and providers)
```

Put logic that can be a pure function in `lib/` and test it there. Components should mostly arrange data that `lib/` already shaped.

## Data layer

- The contract is `src/api/schemas.ts` (zod). It describes the planned `/api/v1/*` endpoints from `../docs/TIER_3/PLAN.md` (section 5). **The backend does not serve these yet**, and `../backend/` is not part of frontend work.
- `VITE_USE_MOCK` defaults to `true`: pages are served by `api/mock/`, which runs the fixtures through the same schemas, so a fixture that drifts from the contract fails in tests. Set `VITE_USE_MOCK=false` to call the real API at `VITE_API_BASE_URL` (default `/api/v1`, proxied by Vite to `http://localhost:8000`). Copy `.env.example` to `.env.local`.
- Pages read data only through the hooks in `api/queries.ts` (`useOverview`, `useStations`, `useStationForecast`, `useGrapAlerts`, `useModelHealth`, `useBacktest`, `useHealth`). Do not call `fetch` from components.
- Loading, error and stale are all handled: each page shows a skeleton, an `ErrorState` with "Try again", and a `StaleBanner` when the server says the data is stale. Show ages against the server clock (`generatedAt`), not the browser's.
- All times are `Asia/Kolkata`. Format them with `lib/format.ts`; never call `toLocaleString` directly.

## Styling rules

- **No raw hex values or arbitrary colours in components.** Colours, type sizes and spacing come from `design/tokens.ts`, which feeds `tailwind.config.ts` and the SVG charts.
- Tailwind class names follow the nested token keys: `bg-grap-bg`, `border-grap-rule`, `bg-status-active-bg`, `text-fresh-late`, `bg-inverse` / `text-inverse-text`, `fill-map-land`. There is no `bg-grap`. When a class has no effect, check the token key before anything else.
- Type sizes are pixel-named (`text-13`, `text-17`, `text-136`). `lib/cn.ts` registers them with `tailwind-merge`; add any new size to that list too, or `text-13 text-ink-muted` will silently drop the size.
- AQI tier colours are literal class strings in `components/aqi/tierClasses.ts` so Tailwind can see them. Do not build class names with template strings.
- Responsive layout is one DOM tree with Tailwind classes (`hidden md:flex`, `md:hidden`). jsdom has no CSS, so tests see both variants: use `getAllBy…(…)[0]` or `within(...)`.
- Cards use `px-5 md:px-7`. The breakpoint for the phone layout is `md` (768 px); the Severe alerts table switches at `lg`.

## Accessibility rules

- Never use colour alone: status is also words (and sr-only text such as "(late)").
- Charts are `role="img"` with a generated description (`describeSeries`), and each has a "View as table" twin. The hover readout is for pointer users only and is `aria-hidden`.
- Tables are real `<table>`s with `th scope`. Scrollable regions are focusable (`tabIndex={0}`, with the lint rule disabled and a comment saying why).
- The map is `role="group"` with a generated label and per-pin links. Station pills are links with `aria-current`, inside a labelled `nav`.
- Focus ring is global (`:focus-visible` in `styles/index.css`). `prefers-reduced-motion` is handled globally in the same file; do not add motion that bypasses it.
- Interactive targets are at least 44 px (`min-h-target`) on touch layouts.

## Charts

`lib/chart.ts` holds the geometry and is pure and tested: viewBox 960 x 340, plot area x 56 to 936, y 10 to 300. Default domains are AQI 150 to 500 and PM2.5 50 to 450, widened in steps of 50 when data leaves them. The shaded zones start at AQI 300 and 400, and PM2.5 120 and 250. `buildChartModel` returns paths, ticks and per-hour `samples`; `nearestSample` drives the readout and `buildSeriesRows` feeds the table. Change the maths in `lib/chart.ts` and its test, not in the component.

## Copy and data honesty

- Copy that depends on data is generated from the data (`lib/leadTime.ts`, `lib/ranking.ts`, the summary sentences). Do not hard-code numbers into sentences.
- A withheld forecast shows an em dash and says why (the 24h PM2.5 forecast is withheld because the model did not beat copy-last in backtests). Always report skill against copy-last.
- The drafted advice text for AQI bands other than "Very Poor" (`lib/advice.ts`, marked REVIEW BEFORE LAUNCH) and the GRAP stage ranges are pending the project owner's review. GRAP thresholds live in one config and are labelled "not an official advisory".
- Design copy kept as written pending review: "Alert fires if skill stays below 0 for 7 days", "Fine particles peak around 7 am and 11 pm", "Nov–Dec 2025".

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

`vercel.json` serves the static build with an SPA rewrite and immutable caching for `/assets/`. On Vercel set `VITE_API_BASE_URL` to the full API URL and `VITE_USE_MOCK=false` once the API exists.

## Status

Built in phases: 1 foundation and tokens, 2 data layer and layout, 3 the four pages, 4 chart readout, table view and phone layouts. Remaining: 5, CI workflow, test gaps (mobile menu, focus handling) and a review pass. Update this section when that lands.

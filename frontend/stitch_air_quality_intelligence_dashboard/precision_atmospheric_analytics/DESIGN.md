---
name: Precision Atmospheric Analytics
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#ffb95f'
  on-secondary: '#472a00'
  secondary-container: '#ee9800'
  on-secondary-container: '#5b3800'
  tertiary: '#ffb2b7'
  on-tertiary: '#67001b'
  tertiary-container: '#ff7886'
  on-tertiary-container: '#780021'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#ffddb8'
  secondary-fixed-dim: '#ffb95f'
  on-secondary-fixed: '#2a1700'
  on-secondary-fixed-variant: '#653e00'
  tertiary-fixed: '#ffdadb'
  tertiary-fixed-dim: '#ffb2b7'
  on-tertiary-fixed: '#40000d'
  on-tertiary-fixed-variant: '#92002a'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 2.25rem
    fontWeight: '600'
    lineHeight: 2.75rem
    letterSpacing: -0.025em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 1.5rem
    fontWeight: '600'
    lineHeight: 2rem
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: '500'
    lineHeight: 1.5rem
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.25rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1rem
  metric-display:
    fontFamily: JetBrains Mono
    fontSize: 2rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.03em
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '500'
    lineHeight: 1rem
    letterSpacing: 0.02em
  label-caps:
    fontFamily: Inter
    fontSize: 0.6875rem
    fontWeight: '600'
    lineHeight: 0.875rem
    letterSpacing: 0.06em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.25rem
  margin: 1rem
  margin-desktop: 1.5rem
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
---

## Brand & Style

This design system targets atmospheric researchers, municipal policymakers, and environmental intelligence officers who operate under mission-critical conditions. The interface prioritizes rapid situational awareness, uncompromised signal fidelity, and rigorous analytical density.

The visual style blends **Technical Minimalism** with **Structured HUD (Heads-Up Display) Data Architecture**. Visual ornamentation is discarded in favor of:
- High contrast, dark canvas foundations that minimize ocular fatigue during extended shifts.
- Structural hairline dividers defining tabular frameworks, geospatial views, and simulation matrices.
- Color reserved almost exclusively for categorical air quality standards (CPCB/NAAQS thresholds and GRAP mitigation stages), telemetry status, and causal counterfactual branches.
- Monospaced typography for tabular data arrays, sensor telemetry IDs, and coordinate stamps to guarantee vertical scanning alignment.

## Colors

The foundation is built on deep obsidian and cool slate to anchor luminous sensor data overlays:
- **Base Canvas (`#0B0F19`)**: Structural dark field for deep spatial depth and minimal glare.
- **Card/Surface (`#111827`)**: Elevated dashboard container background.
- **Surface Highlight (`#1E293B`)**: Hover states, active row selections, and segmented switch tracks.
- **Precision Border (`#1F2937`)**: Hairline delineation between analytical panels.
- **Border Focus (`#374151`)**: Active or hovered perimeter lines.

### Regulatory AQI & Policy State Scales
- **Good / Satisfactory (0–100 AQI)**: Emerald (`#10B981`)
- **Moderate (101–200 AQI)**: Amber (`#F59E0B`)
- **Poor (201–300 AQI)**: Orange (`#F97316`)
- **Very Poor (301–400 AQI)**: Rose Crimson (`#F43F5E`)
- **Severe / Emergency (401–500+ AQI, GRAP IV)**: Violet Maroon (`#A855F7` to `#7E22CE`)
- **Telemetry Cyan (`#06B6D4`)**: Model confidence intervals, causal counterfactual lines, and neutral synthetic controls.

## Typography

Typography establishes an unambiguous visual hierarchy between contextual prose and numerical telemetry:
- **Inter** handles narrative structure, control labeling, analytical metadata, and contextual notes. It ensures low visual strain and legibility across dense dashboard layouts.
- **JetBrains Mono** is enforced across all quantitative data: raw particulate telemetry (PM2.5, PM10, NO2), synthetic control coefficients, geospatial coordinates (Lat/Long), UTC timestamps, and delta indicators.
- **Case Rules**: Section anchors and table headers use uppercase `label-caps` with intentional tracking (`0.06em`) to frame dense data blocks cleanly.

## Layout & Spacing

The system deploys an ultra-dense, multi-column modular grid optimized for 1440px and 1920px monitoring stations:
- **Grid Architecture**: 12-column desktop grid with a compact 1.25rem gutter (`gutter-desktop`) and 1.5rem viewport margins (`margin-desktop`).
- **Dashboard Modules**: Metric telemetry blocks operate on strict multiples of 4px. Card internal padding is locked to `space-md` (0.75rem) or `space-lg` (1rem) to prevent empty space from pushing actionable data below the fold.
- **Adaptive Reflow**:
  - **Desktop (≥ 1280px)**: 12 columns. Fixed temporal scrubber at bottom, split geospatial map (7 cols) and causal impact tree (5 cols).
  - **Tablet (768px – 1279px)**: 6 columns. Collapsible parameter drawers, stacked geospatial and chart views with fixed KPI header bands.
  - **Mobile (< 768px)**: Single column with horizontal swipe-tabs for stations (Anand Vihar, ITO, RK Puram) and GRAP stage status strips.

## Elevation & Depth

This system avoids heavy drop shadows and fuzzy ambient spreads, which introduce perceptual noise in data-heavy dark modes. Depth is achieved via **tonal stratification and structural borders**:

1. **Surface 0 (Canvas `#0B0F19`)**: Ground plane for application background and map canvas.
2. **Surface 1 (Card `#111827`)**: Data cards and spatial panels bounded by a 1px solid `#1F2937` border.
3. **Surface 2 (Float/Dock `#1E293B`)**: Dropdown menus, tooltips, and floating spatial controls. Bounded by 1px solid `#374151` with an ultra-subtle directional occluding shadow: `0 4px 16px -2px rgba(0, 0, 0, 0.6)`.
4. **Data Overlays & Glass**: For geospatial HUD elements hovering directly over dynamic vector tiles, apply `backdrop-filter: blur(8px)` with an 85% alpha background (`rgba(17, 24, 39, 0.85)`).
5. **Glow Accents**: Restrictive, low-spread outer glows (e.g., `0 0 12px rgba(244, 63, 94, 0.35)`) are permitted only for active Severe/Emergency alerts and live sensor anomalies.

## Shapes

The design uses an intentional, precise corner radius system (`roundedness: 1`):
- **Base Components**: Inputs, metric modules, buttons, and segmented control chips use `0.25rem` (4px). This preserves crisp, instrument-like contours.
- **Containers**: Analytical cards and overlay sheets use `rounded-lg` (`0.5rem` / 8px).
- **Badges and Status Dots**: Badges use `0.25rem` or fully circular indicators (`9999px`) for real-time pulsing status beacons. Pill shapes are strictly avoided for actionable buttons to maintain an industrial, scientific aesthetic.

## Components

### Buttons & Trigger Controls
- **Primary Action (Execute Model / Run Counterfactual)**: Background `#10B981`, foreground `#0B0F19`, font weight 600, padding `0.5rem 1rem`. Hover: `#059669`.
- **Secondary / Ghost (Filter / Export)**: Background transparent, border 1px solid `#1F2937`, text `#94A3B8`. Hover: `#1E293B` background, border `#374151`, text `#F8FAFC`.
- **Destructive / Override**: Dark red surface (`rgba(244, 63, 94, 0.1)`), border 1px solid `#F43F5E`, text `#F43F5E`.

### KPI Telemetry Badges & Chips
- Compact dimensions: Height 22px, font `JetBrains Mono`, 11px, weight 500.
- State-mapped background tints (15% opacity) with matching 1px border:
  - Good: `rgba(16, 185, 129, 0.15)` border `rgba(16, 185, 129, 0.4)` text `#34D399`
  - Severe: `rgba(168, 85, 247, 0.15)` border `rgba(168, 85, 247, 0.4)` text `#C084FC`

### Cards & Data Panels
- Background `#111827`, border 1px solid `#1F2937`, internal padding `1rem`.
- Panel Header: Flex row, uppercase tracking label (`label-caps`) on the left, trailing station code / sync timestamp in `label-code`.
- A 1px subtle divider (`#1F2937`) separates the header from the data visualization viewport.

### Form Inputs & Policy Scenario Sliders
- Input fields: Background `#0B0F19`, border 1px solid `#1F2937`, text `#F8FAFC`, placeholder `#475569`. Focus ring: 1px solid `#10B981` (no fuzzy glow).
- Sliders (e.g., Agricultural Stubble Burn Reduction %): Track height 4px, background `#1F2937`, active fill `#10B981`, thumb 14px square (or 4px-radius square), thumb color `#F8FAFC` with border `#10B981`.

### Data Tables (Monitoring Stations & Biomass Fires)
- Header: `#0B0F19`, font `label-caps`, color `#64748B`, height 32px.
- Row: Height 36px, border-bottom 1px solid `#1F2937`, font `body-sm` (text) and `label-code` (values). Alternate row striping is omitted; use subtle hover highlight (`#1E293B`) to trace horizontal lines.

### Causal Policy Evaluation Tree / Graph Cards
- Container holding synthetic controls versus factual observation series.
- Legend placed inline at top right using 8px square swatches (Solid Emerald for Observed AQI, Dashed Cyan for Synthetic Policy Counterfactual).
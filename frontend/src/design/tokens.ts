/**
 * Design tokens, extracted from the "Delhi Air Forecast Dashboard" design
 * (docs/design/). This file is the single source of truth: tailwind.config.ts
 * compiles it into utility classes and SVG charts import it for fills/strokes,
 * so no raw hex belongs in components.
 *
 * It is imported by tailwind.config.ts (a Node context), so keep it free of
 * browser/Vite-only imports.
 */

/** Neutral surfaces, lines and text. */
export const neutral = {
  page: '#F5F6F4',
  surface: '#FFFFFF',
  /** Recessed fills: segmented-control tracks, map land, skeletons. */
  wash: '#F0F2EE',
  line: {
    DEFAULT: '#E3E5E1',
    soft: '#ECEEEA',
    strong: '#DADDD8',
  },
  ink: {
    DEFAULT: '#15171A',
    2: '#3B4046',
    muted: '#5E646B',
    /** Graphics/icons only (3.2:1 on white); never body text. */
    subtle: '#8A9097',
    /** Placeholder glyphs only (2.3:1 on white); never body text. */
    faint: '#A6ABB0',
  },
} as const

/** The dark "what to do" panel. */
export const inverse = {
  DEFAULT: '#15171A',
  text: '#F1F2EF',
  soft: '#CDD1D5',
  muted: '#B4B9BF',
  line: '#33373C',
  accent: '#E0803E',
} as const

export const accent = {
  DEFAULT: '#2B4C7E',
  dark: '#1C3559',
  tint: '#DCE5F1',
} as const

/** Logo stroke. */
export const brand = '#C4463E'

export const caution = { bg: '#FBF1DC', fg: '#6E5612' } as const

/** Skill / delta colours (text on white). */
export const outcome = {
  positive: '#2C5A39',
  negative: '#8E2C26',
  neutral: '#5E646B',
} as const

export type AqiTierKey =
  | 'good'
  | 'satisfactory'
  | 'moderate'
  | 'poor'
  | 'veryPoor'
  | 'severe'

export interface AqiTierTokens {
  /** Scale bar, map dot, chart marker. */
  solid: string
  /** Pill background. */
  bg: string
  /** Pill text. */
  fg: string
  /** Text colour that stays legible on top of `solid` (map dots). */
  onSolid: string
}

/** CPCB six-tier scale. `onSolid` is checked for contrast in tokens.test.ts. */
export const aqiTier: Record<AqiTierKey, AqiTierTokens> = {
  good: { solid: '#4E9A62', bg: '#DDEEE1', fg: '#2C5A39', onSolid: '#15171A' },
  satisfactory: { solid: '#9BB547', bg: '#EAF0D8', fg: '#4B5D1C', onSolid: '#15171A' },
  moderate: { solid: '#D8B03C', bg: '#F6EDCF', fg: '#6E5612', onSolid: '#15171A' },
  poor: { solid: '#E0803E', bg: '#F9E3D2', fg: '#8A4718', onSolid: '#15171A' },
  veryPoor: { solid: '#C4463E', bg: '#F6DEDB', fg: '#8E2C26', onSolid: '#FFFFFF' },
  severe: { solid: '#7B2342', bg: '#EBD9DF', fg: '#6A1D38', onSolid: '#FFFFFF' },
}

/** Operations-table status pills. */
export const alertStatus = {
  active: { bg: aqiTier.severe.bg, fg: aqiTier.severe.fg },
  new: { bg: accent.tint, fg: accent.dark },
  watch: { bg: neutral.wash, fg: neutral.ink[2] },
} as const

/** Stylised Delhi map. */
export const map = {
  land: neutral.surface,
  outline: neutral.line.strong,
  river: '#B8CBDD',
  riverLabel: '#6E8AA6',
} as const

/** Data-freshness strip cells. */
export const freshness = { ok: '#B9C9DB', gap: '#E0803E', late: '#8A4718' } as const

/** GRAP stage card when the stage is in force (Stage II in the design). */
export const grapActive = { bg: '#8E2C26', rule: '#B2584F' } as const

/** Everything Tailwind needs, keyed by utility name. */
export const tailwindColors = {
  page: neutral.page,
  surface: neutral.surface,
  wash: neutral.wash,
  line: neutral.line,
  ink: neutral.ink,
  inverse,
  accent,
  brand,
  caution,
  outcome,
  aqi: {
    good: { DEFAULT: aqiTier.good.solid, bg: aqiTier.good.bg, fg: aqiTier.good.fg, on: aqiTier.good.onSolid },
    satisfactory: { DEFAULT: aqiTier.satisfactory.solid, bg: aqiTier.satisfactory.bg, fg: aqiTier.satisfactory.fg, on: aqiTier.satisfactory.onSolid },
    moderate: { DEFAULT: aqiTier.moderate.solid, bg: aqiTier.moderate.bg, fg: aqiTier.moderate.fg, on: aqiTier.moderate.onSolid },
    poor: { DEFAULT: aqiTier.poor.solid, bg: aqiTier.poor.bg, fg: aqiTier.poor.fg, on: aqiTier.poor.onSolid },
    'very-poor': { DEFAULT: aqiTier.veryPoor.solid, bg: aqiTier.veryPoor.bg, fg: aqiTier.veryPoor.fg, on: aqiTier.veryPoor.onSolid },
    severe: { DEFAULT: aqiTier.severe.solid, bg: aqiTier.severe.bg, fg: aqiTier.severe.fg, on: aqiTier.severe.onSolid },
  },
  status: {
    active: alertStatus.active,
    new: alertStatus.new,
    watch: alertStatus.watch,
  },
  map,
  fresh: freshness,
  grap: grapActive,
} as const

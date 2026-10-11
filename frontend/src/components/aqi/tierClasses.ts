import type { AqiTierKey } from '@/design/tokens'

/**
 * Tailwind classes per CPCB tier. Class names must appear as complete literal
 * strings (never built by concatenation) or Tailwind's scanner drops them.
 */
export const TIER_PILL: Record<AqiTierKey, string> = {
  good: 'bg-aqi-good-bg text-aqi-good-fg',
  satisfactory: 'bg-aqi-satisfactory-bg text-aqi-satisfactory-fg',
  moderate: 'bg-aqi-moderate-bg text-aqi-moderate-fg',
  poor: 'bg-aqi-poor-bg text-aqi-poor-fg',
  veryPoor: 'bg-aqi-very-poor-bg text-aqi-very-poor-fg',
  severe: 'bg-aqi-severe-bg text-aqi-severe-fg',
}

/** Solid dot/marker fill with a label colour that stays legible on it. */
export const TIER_SOLID: Record<AqiTierKey, string> = {
  good: 'bg-aqi-good text-aqi-good-on',
  satisfactory: 'bg-aqi-satisfactory text-aqi-satisfactory-on',
  moderate: 'bg-aqi-moderate text-aqi-moderate-on',
  poor: 'bg-aqi-poor text-aqi-poor-on',
  veryPoor: 'bg-aqi-very-poor text-aqi-very-poor-on',
  severe: 'bg-aqi-severe text-aqi-severe-on',
}

/** Fill only, for dots and scale segments. */
export const TIER_FILL: Record<AqiTierKey, string> = {
  good: 'bg-aqi-good',
  satisfactory: 'bg-aqi-satisfactory',
  moderate: 'bg-aqi-moderate',
  poor: 'bg-aqi-poor',
  veryPoor: 'bg-aqi-very-poor',
  severe: 'bg-aqi-severe',
}

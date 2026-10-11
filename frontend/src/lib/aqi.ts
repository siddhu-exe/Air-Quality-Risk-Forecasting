import { aqiTier, type AqiTierKey, type AqiTierTokens } from '@/design/tokens'

/** Top of the CPCB scale, used to place markers on the 0-500 bar. */
export const AQI_SCALE_MAX = 500

/** The CPCB "Severe" line: an AQI of 401 or more. */
export const SEVERE_THRESHOLD = 401

export interface AqiCategory {
  key: AqiTierKey
  label: string
  /** Lowest integer AQI in the band. */
  min: number
  /** Highest integer AQI in the band; `null` for the open-ended top band. */
  max: number | null
}

/** CPCB six-tier classification. Bands are on the integer (rounded) AQI. */
export const AQI_CATEGORIES: readonly AqiCategory[] = [
  { key: 'good', label: 'Good', min: 0, max: 50 },
  { key: 'satisfactory', label: 'Satisfactory', min: 51, max: 100 },
  { key: 'moderate', label: 'Moderate', min: 101, max: 200 },
  { key: 'poor', label: 'Poor', min: 201, max: 300 },
  { key: 'veryPoor', label: 'Very Poor', min: 301, max: 400 },
  { key: 'severe', label: 'Severe', min: 401, max: null },
]

const SEVERE_CATEGORY = AQI_CATEGORIES[AQI_CATEGORIES.length - 1] as AqiCategory

/** Category for an AQI value. Rounds first, as CPCB reports integer AQI. */
export function categoryOf(aqi: number): AqiCategory {
  if (!Number.isFinite(aqi)) throw new RangeError(`AQI must be a finite number, got ${aqi}`)
  const rounded = Math.round(aqi)
  return AQI_CATEGORIES.find((c) => c.max === null || rounded <= c.max) ?? SEVERE_CATEGORY
}

export function tierTokens(aqi: number): AqiTierTokens {
  return aqiTier[categoryOf(aqi).key]
}

/** Flex weights of the six segments on the scale bar (they sum to 500). */
export const AQI_SCALE_SEGMENTS: readonly { key: AqiTierKey; weight: number }[] = [
  { key: 'good', weight: 50 },
  { key: 'satisfactory', weight: 50 },
  { key: 'moderate', weight: 100 },
  { key: 'poor', weight: 100 },
  { key: 'veryPoor', weight: 100 },
  { key: 'severe', weight: 100 },
]

/** Position of an AQI on the 0-500 bar as a percentage, clamped to the bar. */
export function scalePercent(aqi: number): number {
  const clamped = Math.min(Math.max(aqi, 0), AQI_SCALE_MAX)
  return (clamped / AQI_SCALE_MAX) * 100
}

/** Whole-number AQI for display. */
export function formatAqi(aqi: number): string {
  return String(Math.round(aqi))
}

/** "301-400", "401+" style label for a category band (en dash). */
export function categoryRange(category: AqiCategory): string {
  return category.max === null ? `${category.min}+` : `${category.min}–${category.max}`
}

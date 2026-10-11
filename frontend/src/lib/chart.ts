import { hoursBetween } from './format'

export type ChartTarget = 'aqi' | 'pm25'

/** viewBox of the station chart; everything below is in these units. */
export const CHART = { width: 960, height: 340, left: 56, right: 936, top: 10, bottom: 300 } as const

interface Domain {
  lo: number
  hi: number
}

/** Default value ranges: they keep the interesting winter band readable. */
const DEFAULT_DOMAIN: Record<ChartTarget, Domain> = {
  aqi: { lo: 150, hi: 500 },
  pm25: { lo: 50, hi: 450 },
}

/** Where the shaded "Very Poor" and "Severe" zones begin, in each measure's own units. */
export const ZONE_START: Record<ChartTarget, { veryPoor: number; severe: number }> = {
  aqi: { veryPoor: 300, severe: 400 },
  // CPCB PM2.5 breakpoints: Very Poor above 120 µg/m³, Severe above 250 µg/m³.
  pm25: { veryPoor: 120, severe: 250 },
}

/** The default range, widened in steps of 50 whenever the data would leave it. */
export function chartDomain(target: ChartTarget, values: readonly number[]): Domain {
  const base = DEFAULT_DOMAIN[target]
  if (values.length === 0) return base
  return {
    lo: Math.min(base.lo, Math.floor(Math.min(...values) / 50) * 50),
    hi: Math.max(base.hi, Math.ceil(Math.max(...values) / 50) * 50),
  }
}

export interface ChartInput {
  target: ChartTarget
  /** Oldest first; the last point is "now". */
  history: readonly { t: string; value: number }[]
  /** From "now" (hour 0) to the horizon. */
  forecast: readonly { t: string; median: number; lo: number; hi: number }[]
}

interface Band {
  y: number
  height: number
}

/** One hoverable hour on the chart. "Now" counts as measured. */
export interface ChartSample {
  t: string
  x: number
  /** Where the dot sits: the measured value, or the forecast median. */
  y: number
  kind: 'measured' | 'forecast'
  value: number
  /** Likely range, forecast hours only. */
  lo?: number
  hi?: number
}

export interface ChartModel {
  domain: Domain
  nowX: number
  midX: number
  /** `M x,y L x,y ...` strings ready for an SVG path. */
  pastPath: string
  medianPath: string
  bandPath: string
  persistencePath: string
  ticks: { y: number; labelY: number; label: string }[]
  /** Every hour on the chart, left to right, for the hover readout. */
  samples: ChartSample[]
  severeZone: Band
  veryPoorZone: Band
  horizonHours: number
  endLabel: string
  nowValue: number
  endValue: number
}

const fmt = (n: number): string => n.toFixed(1)

/** Pure geometry for the station chart: no React, so it is unit-testable. */
export function buildChartModel({ target, history, forecast }: ChartInput): ChartModel {
  const first = history[0]
  const last = history[history.length - 1]
  const forecastEnd = forecast[forecast.length - 1]
  if (!first || !last || !forecastEnd) throw new RangeError('A chart needs history and a forecast.')

  const nowIso = last.t
  const pastHours = -hoursBetween(first.t, nowIso)
  const horizonHours = hoursBetween(forecastEnd.t, nowIso)
  const totalHours = pastHours + horizonHours
  const plotWidth = CHART.right - CHART.left

  const domain = chartDomain(target, [
    ...history.map((p) => p.value),
    ...forecast.flatMap((p) => [p.lo, p.hi]),
  ])
  const x = (iso: string): number => CHART.left + ((pastHours + hoursBetween(iso, nowIso)) / totalHours) * plotWidth
  const y = (value: number): number => {
    const clamped = Math.min(Math.max(value, domain.lo), domain.hi)
    return CHART.bottom - ((clamped - domain.lo) / (domain.hi - domain.lo)) * (CHART.bottom - CHART.top)
  }
  const point = (px: number, py: number): string => `${fmt(px)},${fmt(py)}`

  const upper = forecast.map((p) => point(x(p.t), y(p.hi)))
  const lower = forecast.map((p) => point(x(p.t), y(p.lo))).reverse()
  const nowY = y(last.value)
  const samples: ChartSample[] = [
    ...history.map((p): ChartSample => ({ t: p.t, x: x(p.t), y: y(p.value), kind: 'measured', value: p.value })),
    // Hour 0 of the forecast is "now", already covered by the last measured hour.
    ...forecast
      .filter((p) => hoursBetween(p.t, nowIso) > 0)
      .map(
        (p): ChartSample => ({ t: p.t, x: x(p.t), y: y(p.median), kind: 'forecast', value: p.median, lo: p.lo, hi: p.hi }),
      ),
  ]
  const zones = ZONE_START[target]

  const tickValues: number[] = []
  for (let t = Math.floor(domain.lo / 100) * 100; t <= domain.hi; t += 100) {
    if (t > domain.lo) tickValues.push(t)
  }

  return {
    domain,
    nowX: x(nowIso),
    midX: CHART.left + ((pastHours - 36) / totalHours) * plotWidth,
    pastPath: `M${history.map((p) => point(x(p.t), y(p.value))).join(' L')}`,
    medianPath: `M${forecast.map((p) => point(x(p.t), y(p.median))).join(' L')}`,
    bandPath: `M${upper.join(' L')} L${lower.join(' L')} Z`,
    persistencePath: `M${point(x(nowIso), nowY)} L${point(CHART.right, nowY)}`,
    ticks: tickValues.map((value) => ({ y: y(value), labelY: y(value) + 4, label: String(value) })),
    samples,
    severeZone: { y: y(domain.hi), height: y(zones.severe) - y(domain.hi) },
    veryPoorZone: { y: y(zones.severe), height: y(zones.veryPoor) - y(zones.severe) },
    horizonHours,
    endLabel: `+${Math.round(horizonHours)}h`,
    nowValue: last.value,
    endValue: forecastEnd.median,
  }
}

/** One sentence for screen readers: the shape of the line, not every point. */
export function describeSeries(
  subject: string,
  measure: string,
  model: Pick<ChartModel, 'nowValue' | 'endValue' | 'endLabel'>,
  firstValue: number,
): string {
  const delta = model.nowValue - firstValue
  const trend = Math.abs(delta) < 5 ? 'steady at' : delta > 0 ? 'rising to' : 'falling to'
  return `${subject}: ${measure} over the past 72 hours ${trend} ${Math.round(model.nowValue)}, forecast ${Math.round(
    model.endValue,
  )} at ${model.endLabel}`
}

/** The sample closest to a horizontal position in chart units. */
export function nearestSample(samples: readonly ChartSample[], x: number): ChartSample | undefined {
  let best: ChartSample | undefined
  for (const sample of samples) {
    if (!best || Math.abs(sample.x - x) < Math.abs(best.x - x)) best = sample
  }
  return best
}

export interface SeriesRow {
  t: string
  measured?: number
  forecast?: { median: number; lo: number; hi: number }
}

/** The chart's numbers as table rows, oldest first; "now" carries both the reading and the forecast's hour 0. */
export function buildSeriesRows({ history, forecast }: Pick<ChartInput, 'history' | 'forecast'>): SeriesRow[] {
  const rows = new Map<string, SeriesRow>()
  for (const p of history) rows.set(p.t, { t: p.t, measured: p.value })
  for (const p of forecast) {
    const forecastCell = { median: p.median, lo: p.lo, hi: p.hi }
    const row = rows.get(p.t)
    if (row) row.forecast = forecastCell
    else rows.set(p.t, { t: p.t, forecast: forecastCell })
  }
  return [...rows.values()].sort((a, b) => Date.parse(a.t) - Date.parse(b.t))
}

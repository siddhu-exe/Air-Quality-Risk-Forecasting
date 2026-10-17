import type { Evidence, Forecast, PastForecast, ProductKey, StationSummary } from '@/api/schemas'
import type { ChartInput } from '@/lib/chart'

/** A short label for a reason the forecast job recorded; the full text stays available as the tooltip / screen-reader text. */
export function reasonLabel(reason: string): string {
  const r = reason.toLowerCase()
  if (r.startsWith('stale')) return 'Stale data'
  if (r.includes('has not run recently')) return 'Forecast job not running'
  if (r.startsWith('current aqi missing')) return 'No current AQI'
  if (r.startsWith('insufficient history')) return 'Not enough history'
  if (r.includes('core features') || r.includes('required feature group')) return 'Inputs missing'
  if (r.startsWith('no current')) return 'No current reading'
  if (r.startsWith('no valid current hourly aqi')) return 'No hourly AQI'
  if (r.startsWith('hourly aqi rebuilds')) return 'Data mismatch'
  if (r.startsWith('no 24h pm2.5')) return 'Not published'
  return 'No forecast'
}

export function findForecast(forecasts: readonly Forecast[], product: ProductKey): Forecast | undefined {
  return forecasts.find((f) => f.product === product)
}

/** The newest forecast ever issued for a product, while there is no current one (history, never a forecast for now). */
export function lastIssued(forecasts: readonly Forecast[], product: ProductKey): PastForecast | null {
  return findForecast(forecasts, product)?.lastIssued ?? null
}

/** The newest issue time among the stations' last-issued forecasts, or null when none was ever issued. */
export function newestIssue(stations: readonly { forecasts: readonly Forecast[] }[]): string | null {
  let newest: string | null = null
  for (const station of stations) {
    for (const forecast of station.forecasts) {
      const issued = forecast.lastIssued?.issuedAt ?? null
      if (issued !== null && (newest === null || Date.parse(issued) > Date.parse(newest))) newest = issued
    }
  }
  return newest
}

/** The badge that says what kind of forecast this is: a rule, an experimental model, or a model. */
export function kindBadge(forecast: Pick<Forecast, 'kind' | 'experimental'>): string {
  if (forecast.experimental) return 'Experimental'
  return forecast.kind === 'rule' ? 'Rule-based' : 'Model'
}

/** Stations from worst to best right now; stations without a current reading go last, keeping the API's order. */
export function rankByNow<T extends { now: { value: number } | null }>(stations: readonly T[]): T[] {
  const value = (s: T): number => (s.now === null ? Number.NEGATIVE_INFINITY : s.now.value)
  return [...stations].sort((a, b) => value(b) - value(a))
}

/** Same ordering for the stations list, which carries `aqiNow`. */
export function rankSummariesByNow(stations: readonly StationSummary[]): StationSummary[] {
  const value = (s: StationSummary): number => (s.aqiNow === null ? Number.NEGATIVE_INFINITY : s.aqiNow)
  return [...stations].sort((a, b) => value(b) - value(a))
}

export interface Outlook {
  /** Mean of the stations that have an ok forecast; null when none has. */
  mean: number | null
  /** Stations with an ok forecast / stations in the network. */
  count: number
  total: number
}

/** City-level view of one product: the mean over the stations that have it, and how many that is. */
export function outlook(stations: readonly { forecasts: readonly Forecast[] }[], product: ProductKey): Outlook {
  const values = stations
    .map((s) => findForecast(s.forecasts, product))
    .filter((f): f is Forecast => f?.status === 'ok' && f.value !== null)
    .map((f) => f.value as number)
  return {
    mean: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
    count: values.length,
    total: stations.length,
  }
}

/** The ok forecasts as chart points after "now". */
export function chartForecast(forecasts: readonly Forecast[]): ChartInput['forecast'] {
  return forecasts
    .filter((f): f is Forecast & { value: number; validAt: string } => f.status === 'ok' && f.value !== null && f.validAt !== null)
    .map((f) => ({ t: f.validAt, value: f.value }))
    .sort((a, b) => Date.parse(a.t) - Date.parse(b.t))
}

export const isTestWindow = (e: Evidence): boolean => e.window.startsWith('test')
export const isReplayWindow = (e: Evidence): boolean => e.window.startsWith('replay')

export function evidenceFor(evidence: readonly Evidence[], product: ProductKey, window: 'test' | 'replay'): Evidence | undefined {
  return evidence.find((e) => e.product === product && (window === 'test' ? isTestWindow(e) : isReplayWindow(e)))
}

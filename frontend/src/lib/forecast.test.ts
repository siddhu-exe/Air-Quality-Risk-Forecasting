import { describe, expect, it } from 'vitest'
import { makeForecast } from '@/api/mock/data'
import type { Evidence } from '@/api/schemas'
import { chartForecast, evidenceFor, kindBadge, outlook, rankByNow, rankSummariesByNow, reasonLabel } from './forecast'

describe('reasonLabel', () => {
  it.each([
    ['stale: newest reading is 4.6 h older than the issue hour (limit 3 h)', 'Stale data'],
    ['the forecast job has not run recently (newest forecast issued 2026-10-15 09:00)', 'Forecast job not running'],
    ['current AQI missing at the issue hour', 'No current AQI'],
    ['insufficient history: 100 hourly AQI rows in the last 336 h, need 169', 'Not enough history'],
    ['37.8% of the core features are missing (validation limit 22.0%)', 'Inputs missing'],
    ["required feature group 'pm25' is missing for the whole history window", 'Inputs missing'],
    ['no current pm25 value at the issue hour', 'No current reading'],
    ['no valid current hourly AQI, or fewer than 16 valid hours in the 24h window', 'No hourly AQI'],
    ['hourly AQI rebuilds 101.00, stored AQI is 106.00', 'Data mismatch'],
    ['No 24h PM2.5 forecast is published: it does not beat persistence.', 'Not published'],
    ['something the job has never said before', 'No forecast'],
  ])('maps %s to a short label', (reason, label) => {
    expect(reasonLabel(reason)).toBe(label)
  })
})

describe('kindBadge', () => {
  it('tells a rule, a model and an experimental model apart', () => {
    expect(kindBadge(makeForecast('aqi_1h', 'ok'))).toBe('Rule-based')
    expect(kindBadge(makeForecast('aqi_6h', 'ok'))).toBe('Model')
    expect(kindBadge(makeForecast('aqi_24h', 'ok'))).toBe('Experimental')
  })
})

describe('ranking', () => {
  it('puts the worst station first and stations without a reading last, keeping ties in order', () => {
    const at = '2026-10-15T14:00:00+05:30'
    const input = [
      { id: 'a', now: null },
      { id: 'b', now: { value: 300, at, stale: false, category: null } },
      { id: 'c', now: { value: 350, at, stale: false, category: null } },
      { id: 'd', now: { value: 300, at, stale: false, category: null } },
    ]
    expect(rankByNow(input).map((s) => s.id)).toEqual(['c', 'b', 'd', 'a'])
    expect(input[0]?.id).toBe('a')
  })

  it('does the same for the station summaries', () => {
    const base = { name: '', lat: null, lon: null, coordsApproximate: true, categoryNow: null, pm25Now: null, lastReadingAt: null, stale: false }
    const ranked = rankSummariesByNow([
      { ...base, id: 'a', aqiNow: null },
      { ...base, id: 'b', aqiNow: 120 },
      { ...base, id: 'c', aqiNow: 410 },
    ])
    expect(ranked.map((s) => s.id)).toEqual(['c', 'b', 'a'])
  })
})

describe('outlook', () => {
  const stations = [
    { forecasts: [makeForecast('aqi_6h', 'ok', { value: 300 })] },
    { forecasts: [makeForecast('aqi_6h', 'ok', { value: 340 })] },
    { forecasts: [makeForecast('aqi_6h', 'unavailable', { reason: 'stale: ...' })] },
    { forecasts: [] },
  ]

  it('averages only the stations that have the forecast and says how many that is', () => {
    expect(outlook(stations, 'aqi_6h')).toEqual({ mean: 320, count: 2, total: 4 })
  })

  it('has no mean when no station has it, rather than 0', () => {
    expect(outlook(stations, 'pm25_1h')).toEqual({ mean: null, count: 0, total: 4 })
  })
})

describe('chartForecast', () => {
  it('keeps only ok forecasts, soonest first, and never invents a point for the others', () => {
    const points = chartForecast([
      makeForecast('aqi_24h', 'ok', { value: 345 }),
      makeForecast('aqi_1h', 'unavailable', { reason: 'x' }),
      makeForecast('aqi_6h', 'ok', { value: 338 }),
    ])
    expect(points.map((p) => p.value)).toEqual([338, 345])
    expect(chartForecast([makeForecast('aqi_1h', 'unavailable', { reason: 'x' })])).toEqual([])
  })
})

describe('evidenceFor', () => {
  const row = (product: Evidence['product'], window: string): Evidence => ({
    product,
    label: '',
    window,
    n: 1,
    skillVsPersistence: 0.1,
    skillVsPersistenceLo: null,
    skillVsPersistenceHi: null,
    skillVsWindowUpdate: null,
    skillVsWindowUpdateLo: null,
    skillVsWindowUpdateHi: null,
  })

  it('finds the test or replay row of a product', () => {
    const rows = [row('aqi_6h', 'test 2025-11-01..2025-12-31'), row('aqi_6h', 'replay 2026-09-01..2026-10-07')]
    expect(evidenceFor(rows, 'aqi_6h', 'test')?.window).toMatch(/^test/)
    expect(evidenceFor(rows, 'aqi_6h', 'replay')?.window).toMatch(/^replay/)
    expect(evidenceFor(rows, 'aqi_1h', 'test')).toBeUndefined()
  })
})

import { describe, expect, it } from 'vitest'
import { buildChartModel, buildSeriesRows, CHART, chartDomain, describeSeries, nearestSample } from './chart'

const NOW = Date.parse('2026-10-11T14:00:00+05:30')
const at = (h: number): string => new Date(NOW + h * 3_600_000).toISOString()

/** 73 hours of history ending now, and forecast points at +1h, +6h (and +24h when `endHours` is 24). */
function input(target: 'aqi' | 'pm25', nowValue: number, endHours: number, endValue: number) {
  const hours = endHours === 24 ? [1, 6, 24] : [1, 6]
  return {
    target,
    history: Array.from({ length: 73 }, (_, i) => ({ t: at(i - 72), value: nowValue })),
    forecast: hours.map((h) => ({ t: at(h), value: nowValue + ((endValue - nowValue) * h) / endHours })),
  } as const
}

describe('chartDomain', () => {
  it('uses the default range when the data fits', () => {
    expect(chartDomain('aqi', [300, 420])).toEqual({ lo: 150, hi: 500 })
    expect(chartDomain('pm25', [100, 300])).toEqual({ lo: 50, hi: 450 })
  })

  it('widens in steps of 50 when the data leaves the default', () => {
    expect(chartDomain('aqi', [120, 530])).toEqual({ lo: 100, hi: 550 })
    expect(chartDomain('pm25', [20, 480])).toEqual({ lo: 0, hi: 500 })
  })
})

describe('buildChartModel', () => {
  it('puts "now" at 72/96 of the AQI plot, and the end of the forecast at the right edge', () => {
    const model = buildChartModel(input('aqi', 380, 24, 410))
    const plot = CHART.right - CHART.left
    expect(model.nowX).toBeCloseTo(CHART.left + (72 / 96) * plot, 5)
    expect(model.pastPath.startsWith(`M${CHART.left.toFixed(1)},`)).toBe(true)
    expect(model.forecastPath.includes(`${CHART.right.toFixed(1)},`)).toBe(true)
    expect(model.endLabel).toBe('+24h')
  })

  it('compresses the past when the PM2.5 horizon is only 6 hours', () => {
    const model = buildChartModel(input('pm25', 250, 6, 230))
    expect(model.nowX).toBeCloseTo(CHART.left + (72 / 78) * (CHART.right - CHART.left), 5)
    expect(model.endLabel).toBe('+6h')
  })

  it('labels the 100-multiples inside the domain and not the bottom edge', () => {
    expect(buildChartModel(input('aqi', 380, 24, 410)).ticks.map((t) => t.label)).toEqual(['200', '300', '400', '500'])
    expect(buildChartModel(input('pm25', 250, 6, 230)).ticks.map((t) => t.label)).toEqual(['100', '200', '300', '400'])
  })

  it('draws the Severe zone from the 400 line to the top of the plot', () => {
    const model = buildChartModel(input('aqi', 380, 24, 410))
    expect(model.severeZone.y).toBeCloseTo(CHART.top, 5)
    expect(model.veryPoorZone.y).toBeCloseTo(model.severeZone.y + model.severeZone.height, 5)
  })

  it('keeps the flat copy-last baseline at the current value', () => {
    const model = buildChartModel(input('aqi', 380, 24, 410))
    const ys = [...model.persistencePath.matchAll(/,([\d.]+)/g)].map((m) => m[1])
    expect(new Set(ys).size).toBe(1)
  })

  it('rejects a chart with no history rather than drawing nothing', () => {
    expect(() => buildChartModel({ target: 'aqi', history: [], forecast: [] })).toThrow(RangeError)
  })

  it('draws a chart with no forecast at all: no forecast line, a short empty future, no invented end value', () => {
    const model = buildChartModel({ target: 'aqi', history: input('aqi', 380, 24, 410).history, forecast: [] })
    expect(model.forecastPath).toBe('')
    expect(model.endValue).toBeNull()
    expect(model.nowX).toBeCloseTo(CHART.left + (72 / 78) * (CHART.right - CHART.left), 5)
    expect(model.samples.every((s) => s.kind === 'measured')).toBe(true)
  })

  it('starts the forecast line at "now" and passes through every published point', () => {
    const model = buildChartModel(input('aqi', 380, 24, 410))
    expect(model.forecastPath.startsWith(`M${model.nowX.toFixed(1)},`)).toBe(true)
    expect(model.forecastPath.split(' L')).toHaveLength(1 + 3)
  })
})

describe('describeSeries', () => {
  const model = { nowValue: 388, endValue: 412, endLabel: '+24h' }
  it('says when there is no forecast instead of reporting a number', () => {
    expect(describeSeries('ITO', 'AQI', { ...model, endValue: null }, 318)).toContain('no forecast available')
  })

  it('says rising, falling or steady', () => {
    expect(describeSeries('Anand Vihar', 'AQI', model, 318)).toContain('rising to 388')
    expect(describeSeries('Anand Vihar', 'AQI', model, 450)).toContain('falling to 388')
    expect(describeSeries('Anand Vihar', 'AQI', model, 386)).toContain('steady at 388')
    expect(describeSeries('Anand Vihar', 'AQI', model, 318)).toContain('forecast 412 at +24h')
  })
})

describe('chart samples', () => {
  const model = buildChartModel(input('aqi', 380, 24, 410))

  it('has one sample per measured hour plus one per published forecast, with "now" counted once, as measured', () => {
    expect(model.samples).toHaveLength(73 + 3)
    const atNow = model.samples.filter((s) => Math.abs(s.x - model.nowX) < 0.001)
    expect(atNow).toHaveLength(1)
    expect(atNow[0]?.kind).toBe('measured')
  })

  it('marks forecast points as forecast and gives no range: none is published', () => {
    expect(model.samples[0]).toMatchObject({ kind: 'measured', value: 380 })
    expect(model.samples.at(-1)).toMatchObject({ kind: 'forecast', value: 410 })
    expect(Object.keys(model.samples.at(-1) ?? {})).not.toContain('lo')
  })

  it('finds the sample nearest a position, including past either edge', () => {
    const target = model.samples[50]
    expect(target).toBeDefined()
    expect(nearestSample(model.samples, (target?.x ?? 0) + 1)).toBe(target)
    expect(nearestSample(model.samples, -100)).toBe(model.samples[0])
    expect(nearestSample(model.samples, 5000)).toBe(model.samples.at(-1))
    expect(nearestSample([], 100)).toBeUndefined()
  })
})

describe('buildSeriesRows', () => {
  it('merges "now" into one row and keeps time order', () => {
    const rows = buildSeriesRows(input('aqi', 380, 24, 410))
    expect(rows).toHaveLength(73 + 3)
    expect(rows[72]?.measured).toBe(380)
    expect(rows[72]?.forecast).toBeUndefined() // "now" is a reading, not a forecast
    expect(rows[73]?.measured).toBeUndefined()
    expect(rows[73]?.forecast).toBeCloseTo(381.25, 5)
    expect(rows.at(-1)?.forecast).toBe(410)
  })
})

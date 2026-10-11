import { describe, expect, it } from 'vitest'
import { buildChartModel, buildSeriesRows, CHART, chartDomain, describeSeries, nearestSample } from './chart'

const NOW = Date.parse('2026-10-11T14:00:00+05:30')
const at = (h: number): string => new Date(NOW + h * 3_600_000).toISOString()

function input(target: 'aqi' | 'pm25', nowValue: number, endHours: number, endValue: number) {
  return {
    target,
    history: Array.from({ length: 73 }, (_, i) => ({ t: at(i - 72), value: nowValue })),
    forecast: Array.from({ length: endHours + 1 }, (_, j) => ({
      t: at(j),
      median: nowValue + ((endValue - nowValue) * j) / endHours,
      lo: nowValue - 10,
      hi: nowValue + 10 + j,
    })),
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
    expect(model.bandPath.includes(`${CHART.right.toFixed(1)},`)).toBe(true)
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

  it('rejects empty input rather than drawing nothing', () => {
    expect(() => buildChartModel({ target: 'aqi', history: [], forecast: [] })).toThrow(RangeError)
  })
})

describe('describeSeries', () => {
  const model = { nowValue: 388, endValue: 412, endLabel: '+24h' }
  it('says rising, falling or steady', () => {
    expect(describeSeries('Anand Vihar', 'AQI', model, 318)).toContain('rising to 388')
    expect(describeSeries('Anand Vihar', 'AQI', model, 450)).toContain('falling to 388')
    expect(describeSeries('Anand Vihar', 'AQI', model, 386)).toContain('steady at 388')
    expect(describeSeries('Anand Vihar', 'AQI', model, 318)).toContain('forecast 412 at +24h')
  })
})

describe('chart samples', () => {
  const model = buildChartModel(input('aqi', 380, 24, 410))

  it('has one sample per hour, with "now" counted once, as measured', () => {
    expect(model.samples).toHaveLength(73 + 24)
    const atNow = model.samples.filter((s) => Math.abs(s.x - model.nowX) < 0.001)
    expect(atNow).toHaveLength(1)
    expect(atNow[0]?.kind).toBe('measured')
  })

  it('gives forecast hours a likely range and measured hours none', () => {
    expect(model.samples[0]).toMatchObject({ kind: 'measured', value: 380 })
    expect(model.samples[0]?.lo).toBeUndefined()
    expect(model.samples.at(-1)).toMatchObject({ kind: 'forecast', value: 410, lo: 370, hi: 414 })
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
    expect(rows).toHaveLength(73 + 24)
    const now = rows[72]
    expect(now?.measured).toBe(380)
    expect(now?.forecast?.median).toBe(380)
    expect(rows[71]?.forecast).toBeUndefined()
    expect(rows[73]?.measured).toBeUndefined()
    expect(rows.at(-1)?.forecast?.median).toBe(410)
  })
})

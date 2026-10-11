import { AQI_CATEGORIES, AQI_SCALE_SEGMENTS, categoryOf, categoryRange, formatAqi, scalePercent, tierTokens } from './aqi'

describe('categoryOf', () => {
  it.each([
    [0, 'good'],
    [50, 'good'],
    [51, 'satisfactory'],
    [100, 'satisfactory'],
    [101, 'moderate'],
    [200, 'moderate'],
    [201, 'poor'],
    [300, 'poor'],
    [301, 'veryPoor'],
    [400, 'veryPoor'],
    [401, 'severe'],
    [500, 'severe'],
    [620, 'severe'],
  ])('puts AQI %d in %s', (aqi, key) => {
    expect(categoryOf(aqi).key).toBe(key)
  })

  it('rounds before classifying, as CPCB reports integer AQI', () => {
    expect(categoryOf(400.4).key).toBe('veryPoor')
    expect(categoryOf(400.5).key).toBe('severe')
  })

  it('refuses values it cannot classify rather than guessing', () => {
    expect(() => categoryOf(Number.NaN)).toThrow(RangeError)
    expect(() => categoryOf(Infinity)).toThrow(RangeError)
  })

  it('has contiguous bands starting at 0 with an open-ended top', () => {
    expect(AQI_CATEGORIES[0]?.min).toBe(0)
    AQI_CATEGORIES.slice(1).forEach((c, i) => {
      expect(c.min).toBe((AQI_CATEGORIES[i]?.max ?? NaN) + 1)
    })
    expect(AQI_CATEGORIES.at(-1)?.max).toBeNull()
  })
})

describe('scale helpers', () => {
  it('segment weights add up to the 0-500 scale in category order', () => {
    expect(AQI_SCALE_SEGMENTS.reduce((sum, s) => sum + s.weight, 0)).toBe(500)
    expect(AQI_SCALE_SEGMENTS.map((s) => s.key)).toEqual(AQI_CATEGORIES.map((c) => c.key))
  })

  it('places markers as a clamped percentage', () => {
    expect(scalePercent(374)).toBeCloseTo(74.8)
    expect(scalePercent(-5)).toBe(0)
    expect(scalePercent(700)).toBe(100)
  })

  it('formats ranges with an en dash and an open top band', () => {
    expect(categoryRange(categoryOf(350))).toBe('301–400')
    expect(categoryRange(categoryOf(450))).toBe('401+')
  })

  it('formats and tiers a value consistently', () => {
    expect(formatAqi(373.6)).toBe('374')
    expect(tierTokens(374).fg).toBe('#8E2C26')
  })
})

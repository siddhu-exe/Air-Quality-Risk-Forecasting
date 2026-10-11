import { describe, expect, it } from 'vitest'
import { countWord, rankByForecast } from './ranking'

describe('rankByForecast', () => {
  it('orders worst first without mutating the input', () => {
    const input = [{ forecast24h: 300 }, { forecast24h: 410 }, { forecast24h: 350 }]
    expect(rankByForecast(input).map((s) => s.forecast24h)).toEqual([410, 350, 300])
    expect(input[0]?.forecast24h).toBe(300)
  })

  it('keeps the original order for ties', () => {
    const input = [
      { id: 'a', forecast24h: 350 },
      { id: 'b', forecast24h: 350 },
    ]
    expect(rankByForecast(input).map((s) => s.id)).toEqual(['a', 'b'])
  })
})

describe('countWord', () => {
  it('spells out small counts and keeps digits for large ones', () => {
    expect(countWord(2)).toBe('two')
    expect(countWord(12)).toBe('12')
  })
})

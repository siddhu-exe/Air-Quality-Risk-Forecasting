import { AQI_CATEGORIES } from './aqi'
import { ADVICE } from './advice'

describe('advice copy', () => {
  it('covers every CPCB category with a headline, actions and a summary', () => {
    for (const { key } of AQI_CATEGORIES) {
      const advice = ADVICE[key]
      expect(advice.headline.length).toBeGreaterThan(0)
      expect(advice.actions.length).toBeGreaterThanOrEqual(2)
      expect(advice.summary.length).toBeGreaterThan(0)
    }
  })

  it('keeps the design wording for Very Poor', () => {
    expect(ADVICE.veryPoor.headline).toBe('Keep outdoor effort short.')
    expect(ADVICE.veryPoor.actions).toHaveLength(4)
  })
})

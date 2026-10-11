import {
  formatAge,
  formatClock,
  formatDay,
  formatPercent,
  formatSigned,
  formatSkillIndex,
  formatUpdated,
  formatWeekdayClock,
  hoursBetween,
} from './format'

describe('IST formatting', () => {
  it('shows clock time in IST whatever offset the API uses', () => {
    expect(formatClock('2026-10-11T14:00:00+05:30')).toBe('14:00')
    expect(formatClock('2026-10-11T08:30:00Z')).toBe('14:00')
  })

  it('shows midnight as 00:00, never 24:00', () => {
    expect(formatClock('2026-10-10T18:30:00Z')).toBe('00:00')
  })

  it('uses the IST calendar day, not the UTC one', () => {
    // 20:00 UTC on the 10th is already 01:30 IST on the 11th.
    expect(formatDay('2026-10-10T20:00:00Z')).toBe('Sun 11 Oct')
  })

  it('composes the header and table labels', () => {
    expect(formatUpdated('2026-10-11T14:00:00+05:30')).toBe('Updated 14:00 IST · Sun 11 Oct')
    expect(formatWeekdayClock('2026-10-12T14:00:00+05:30')).toBe('Mon 14:00')
  })

  it('rejects an invalid timestamp loudly', () => {
    expect(() => formatClock('not a date')).toThrow(RangeError)
  })
})

describe('number formatting', () => {
  it('formats probabilities as whole percents', () => {
    expect(formatPercent(0.314)).toBe('31%')
    expect(formatPercent(0.998)).toBe('100%')
  })

  it('signs integers with a true minus sign', () => {
    expect(formatSigned(18)).toBe('+18')
    expect(formatSigned(-4)).toBe('−4')
    expect(formatSigned(0.2)).toBe('0')
  })

  it('formats skill indexes to two places without a signed zero', () => {
    expect(formatSkillIndex(0.09)).toBe('+0.09')
    expect(formatSkillIndex(-0.034)).toBe('−0.03')
    expect(formatSkillIndex(0.001)).toBe('0.00')
  })

  it('formats ages', () => {
    expect(formatAge(14 * 60_000)).toBe('14 min')
    expect(formatAge(134 * 60_000)).toBe('2 h 14 min')
    expect(formatAge(120 * 60_000)).toBe('2 h')
    expect(formatAge(-5_000)).toBe('0 min')
  })

  it('measures hours between timestamps', () => {
    expect(hoursBetween('2026-10-12T14:00:00+05:30', '2026-10-11T14:00:00+05:30')).toBe(24)
  })
})

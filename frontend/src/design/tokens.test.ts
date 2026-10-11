import { contrastRatio } from '@/test/contrast'
import { accent, aqiTier, caution, inverse, neutral, outcome, type AqiTierKey } from './tokens'

const AA = 4.5
const tiers = Object.entries(aqiTier) as [AqiTierKey, (typeof aqiTier)[AqiTierKey]][]

describe('design tokens: WCAG AA contrast', () => {
  it.each(tiers)('%s pill text is readable on its pill background', (_key, t) => {
    expect(contrastRatio(t.fg, t.bg)).toBeGreaterThanOrEqual(AA)
  })

  it.each(tiers)('%s map-dot label is readable on the dot', (_key, t) => {
    expect(contrastRatio(t.onSolid, t.solid)).toBeGreaterThanOrEqual(AA)
  })

  it('body and muted text pass on every surface they sit on', () => {
    for (const bg of [neutral.surface, neutral.page, neutral.wash]) {
      expect(contrastRatio(neutral.ink.DEFAULT, bg)).toBeGreaterThanOrEqual(AA)
      expect(contrastRatio(neutral.ink[2], bg)).toBeGreaterThanOrEqual(AA)
      expect(contrastRatio(neutral.ink.muted, bg)).toBeGreaterThanOrEqual(AA)
    }
  })

  it('links, caution badge, outcome colours and the dark panel pass', () => {
    expect(contrastRatio(accent.DEFAULT, neutral.page)).toBeGreaterThanOrEqual(AA)
    expect(contrastRatio(caution.fg, caution.bg)).toBeGreaterThanOrEqual(AA)
    expect(contrastRatio(outcome.positive, neutral.surface)).toBeGreaterThanOrEqual(AA)
    expect(contrastRatio(outcome.negative, neutral.surface)).toBeGreaterThanOrEqual(AA)
    expect(contrastRatio(inverse.text, inverse.DEFAULT)).toBeGreaterThanOrEqual(AA)
    expect(contrastRatio(inverse.muted, inverse.DEFAULT)).toBeGreaterThanOrEqual(AA)
  })

  it('keeps the decorative greys out of text duty (documented as graphics-only)', () => {
    expect(contrastRatio(neutral.ink.subtle, neutral.surface)).toBeGreaterThanOrEqual(3)
    expect(contrastRatio(neutral.ink.faint, neutral.surface)).toBeLessThan(AA)
  })
})

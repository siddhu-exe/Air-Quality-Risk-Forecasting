import { describe, expect, it } from 'vitest'
import { leadTimeNote } from './leadTime'

const base = {
  horizon: '24h',
  episodes: 86,
  modelDetectionRate: 0.698,
  persistenceDetectionRate: 0.651,
  modelLeadHours: 7.4,
  persistenceLeadHours: 5,
} as const

describe('leadTimeNote', () => {
  it('reports lead times when the model catches at least as many episodes', () => {
    expect(leadTimeNote(base)).toBe(
      'When it catches an episode, the first warning comes 7.4 h before onset on average, vs 5.0 h for copy-last.',
    )
  })

  it('admits when copy-last catches more, and whether the model at least warns earlier', () => {
    const six = { ...base, horizon: '6h', modelDetectionRate: 0.839, persistenceDetectionRate: 0.931, modelLeadHours: 2.5, persistenceLeadHours: 0.5 } as const
    expect(leadTimeNote(six)).toBe('Copy-last catches more episodes here; the model warns earlier (2.5 h vs 0.5 h) when it does.')
    expect(leadTimeNote({ ...six, modelLeadHours: 0.4 })).toContain('warns no earlier')
  })
})

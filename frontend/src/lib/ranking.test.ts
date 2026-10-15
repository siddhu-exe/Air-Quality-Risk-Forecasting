import { describe, expect, it } from 'vitest'
import { countWord } from './ranking'

describe('countWord', () => {
  it('spells out small counts and keeps digits for large ones', () => {
    expect(countWord(2)).toBe('two')
    expect(countWord(12)).toBe('12')
  })
})

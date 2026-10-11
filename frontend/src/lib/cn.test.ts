import { describe, expect, it } from 'vitest'
import { cn } from './cn'

describe('cn', () => {
  it('keeps a pixel font size next to a text colour, in either order', () => {
    expect(cn('text-13', 'text-ink-muted')).toBe('text-13 text-ink-muted')
    expect(cn('text-ink-muted', 'text-13')).toBe('text-ink-muted text-13')
  })

  it('still lets a later font size replace an earlier one', () => {
    expect(cn('text-96', 'md:text-136', 'text-56')).toBe('md:text-136 text-56')
  })

  it('resolves ordinary conflicts and drops falsy values', () => {
    expect(cn('px-5', false, undefined, 'px-10')).toBe('px-10')
  })
})

import type { SkillStatus } from '@/lib/skill'

/** Text colour for a skill value or delta. Literal strings so Tailwind keeps them. */
export const OUTCOME_TEXT: Record<SkillStatus, string> = {
  beating: 'text-outcome-positive',
  even: 'text-outcome-neutral',
  losing: 'text-outcome-negative',
}

/** Status pill ("Beating copy-last") and its leading dot. */
export const OUTCOME_PILL: Record<SkillStatus, { pill: string; dot: string }> = {
  beating: { pill: 'bg-aqi-good-bg text-aqi-good-fg', dot: 'bg-aqi-good-fg' },
  even: { pill: 'bg-wash text-ink-2', dot: 'bg-ink-2' },
  losing: { pill: 'bg-aqi-very-poor-bg text-aqi-very-poor-fg', dot: 'bg-aqi-very-poor-fg' },
}

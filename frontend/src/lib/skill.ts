import type { outcome } from '@/design/tokens'

/**
 * Skill = 1 - model error / copy-last error. Within +-0.03 the model and
 * "same as now" are indistinguishable, so we call it a tie rather than a win.
 */
export const SKILL_TIE_BAND = 0.03

export type SkillStatus = 'beating' | 'even' | 'losing'

export function skillStatus(skill: number): SkillStatus {
  if (skill > SKILL_TIE_BAND) return 'beating'
  if (skill < -SKILL_TIE_BAND) return 'losing'
  return 'even'
}

export const SKILL_STATUS_LABEL: Record<SkillStatus, string> = {
  beating: 'Beating copy-last',
  even: 'About even',
  losing: 'Losing to copy-last',
}

/** Key into `outcome` tokens, for colouring a skill value. */
export const SKILL_OUTCOME: Record<SkillStatus, keyof typeof outcome> = {
  beating: 'positive',
  even: 'neutral',
  losing: 'negative',
}

/** Horizon-card text: "≈ same", "+11% MAE", "−9% MAE". */
export function formatSkillMae(skill: number): string {
  if (skillStatus(skill) === 'even') return '≈ same'
  const pct = Math.round(Math.abs(skill) * 100)
  return `${skill > 0 ? '+' : '−'}${pct}% MAE`
}

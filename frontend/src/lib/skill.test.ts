import { SKILL_TIE_BAND, formatSkillMae, skillStatus } from './skill'

describe('skill', () => {
  it('calls anything inside the tie band a tie', () => {
    expect(skillStatus(0)).toBe('even')
    expect(skillStatus(SKILL_TIE_BAND)).toBe('even')
    expect(skillStatus(-SKILL_TIE_BAND)).toBe('even')
  })

  it('separates wins and losses outside the band', () => {
    expect(skillStatus(0.09)).toBe('beating')
    expect(skillStatus(-0.093)).toBe('losing')
  })

  it('formats MAE skill the way the horizon cards do', () => {
    expect(formatSkillMae(0.11)).toBe('+11% MAE')
    expect(formatSkillMae(0.069)).toBe('+7% MAE')
    expect(formatSkillMae(-0.093)).toBe('−9% MAE')
    expect(formatSkillMae(0.01)).toBe('≈ same')
  })
})

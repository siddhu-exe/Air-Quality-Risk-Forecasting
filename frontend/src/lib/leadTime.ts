import type { LeadTime } from '@/api/schemas'

const HORIZON_LABEL = { '24h': '24 hours', '6h': '6 hours' } as const

export const leadTimeHorizonLabel = (horizon: LeadTime['horizon']): string => HORIZON_LABEL[horizon]

const hours = (n: number): string => `${n.toFixed(1)} h`

/** One honest sentence per horizon: who catches more episodes, and who warns earlier. */
export function leadTimeNote(lead: LeadTime): string {
  const { modelLeadHours: m, persistenceLeadHours: p } = lead
  if (lead.modelDetectionRate >= lead.persistenceDetectionRate) {
    return `When it catches an episode, the first warning comes ${hours(m)} before onset on average, vs ${hours(p)} for copy-last.`
  }
  const timing =
    m > p
      ? `the model warns earlier (${hours(m)} vs ${hours(p)}) when it does`
      : `the model warns no earlier (${hours(m)} vs ${hours(p)}) when it does`
  return `Copy-last catches more episodes here; ${timing}.`
}

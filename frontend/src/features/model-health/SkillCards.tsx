import type { ModelHealth, SkillSeriesId } from '@/api/schemas'
import { Sparkline } from '@/components/charts/Sparkline'
import { Card } from '@/components/ui/Card'
import { OUTCOME_PILL } from '@/components/ui/outcomeClasses'
import { formatSkillIndex } from '@/lib/format'
import { SKILL_STATUS_LABEL, skillStatus } from '@/lib/skill'

const SERIES: Record<SkillSeriesId, { title: string; note: string }> = {
  aqi24: {
    title: 'AQI · 24h ahead',
    note: 'The forecast that matters most for GRAP. Alert fires if skill stays below 0 for 7 days.',
  },
  pm25_6: {
    title: 'PM2.5 · 6h ahead',
    note: 'Strongest model. Raw PM2.5 moves hour to hour, so there is room to beat copy-last.',
  },
  aqi1: {
    title: 'AQI · 1h ahead',
    note: 'AQI barely changes in an hour. Expected to stay near zero.',
  },
}

/** Rolling 30-day skill per model, each with its status, trend line and backtest reference. */
export function SkillCards({ skill }: { skill: ModelHealth['skill'] }) {
  return (
    <section aria-label="Rolling 30-day skill" className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
      {skill.map((item) => {
        const { title, note } = SERIES[item.id]
        const status = skillStatus(item.current)
        const pill = OUTCOME_PILL[status]
        const value = formatSkillIndex(item.current)
        return (
          <Card key={item.id} className="flex flex-col gap-3 px-6 py-[22px]">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">{title}</h2>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-12 font-medium ${pill.pill}`}>
                <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${pill.dot}`} />
                {SKILL_STATUS_LABEL[status]}
              </span>
            </div>
            <div className="flex items-baseline gap-2.5">
              <span className="font-mono text-40 leading-none">{value}</span>
              <span className="text-13 text-ink-muted">30-day MAE skill</span>
            </div>
            <Sparkline values={item.series} label={`${title} skill over the last 30 days, ending at ${value}`} />
            <div className="flex justify-between gap-2 border-t border-line-soft pt-2.5 text-13">
              <span className="text-ink-muted">Backtest reference</span>
              <span className="text-right font-mono">{item.referenceLabel}</span>
            </div>
            <p className="text-13 text-ink-2">{note}</p>
          </Card>
        )
      })}
    </section>
  )
}

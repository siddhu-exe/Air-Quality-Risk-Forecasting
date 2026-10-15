import type { ModelHealth, ProductKey } from '@/api/schemas'
import { Sparkline } from '@/components/charts/Sparkline'
import { Card } from '@/components/ui/Card'
import { OUTCOME_PILL } from '@/components/ui/outcomeClasses'
import { formatSkillIndex } from '@/lib/format'
import { kindBadge } from '@/lib/forecast'
import { SKILL_STATUS_LABEL, skillStatus } from '@/lib/skill'

const SERIES: Record<ProductKey, { title: string; note: string }> = {
  aqi_1h: {
    title: 'AQI · 1h ahead',
    note: 'A rule, not a model: it is the reference the 1h forecast is measured against, so skill against it is zero by definition.',
  },
  aqi_6h: {
    title: 'AQI · 6h ahead',
    note: 'The one AQI model with real skill. It is scored against same-as-now and against the 24h-window update.',
  },
  aqi_24h: {
    title: 'AQI · 24h ahead',
    note: 'Experimental: about as accurate as assuming no change. An alert opens if skill stays below 0 for 7 days.',
  },
  pm25_1h: { title: 'PM2.5 · 1h ahead', note: 'Raw PM2.5 moves hour to hour, so there is room to beat same-as-now.' },
  pm25_6h: { title: 'PM2.5 · 6h ahead', note: 'The strongest forecast here, with the largest margin over same-as-now.' },
  pm25_24h: { title: 'PM2.5 · 24h ahead', note: 'Not published.' },
}

function Row({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null
  const status = skillStatus(value)
  const pill = OUTCOME_PILL[status]
  return (
    <div className="flex items-center justify-between gap-2 text-13">
      <span className="text-ink-muted">{label}</span>
      <span className="flex items-center gap-2">
        <span className="font-mono text-15">{formatSkillIndex(value)}</span>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-12 font-medium ${pill.pill}`}>
          <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${pill.dot}`} />
          {SKILL_STATUS_LABEL[status]}
        </span>
      </span>
    </div>
  )
}

/** Rolling 30-day skill per published product, against same-as-now and (for AQI) the 24h-window update. */
export function SkillCards({ skill }: { skill: ModelHealth['skill'] }) {
  return (
    <section aria-label="Rolling 30-day skill" className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
      {skill.map((item) => {
        const { title, note } = SERIES[item.product]
        const series = item.skillVsPersistence.filter((v): v is number => v !== null)
        return (
          <Card key={item.product} className="flex flex-col gap-3 px-6 py-[22px]">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">{title}</h2>
              <span className="rounded bg-wash px-2 py-0.5 text-12 text-ink-2">
                {kindBadge({ kind: item.product === 'aqi_1h' ? 'rule' : 'model', experimental: item.product === 'aqi_24h' })}
              </span>
            </div>
            {item.currentVsPersistence === null ? (
              <p className="py-3 text-ink-2">
                No scored forecasts yet. Skill appears here once live forecasts have matured and been scored.
              </p>
            ) : (
              <>
                <Row label="vs same-as-now" value={item.currentVsPersistence} />
                {item.product !== 'aqi_1h' && <Row label="vs 24h-window update" value={item.currentVsWindowUpdate} />}
                {series.length >= 2 && (
                  <Sparkline
                    values={series}
                    label={`${title} 30-day skill against same-as-now over the last ${series.length} days, ending at ${formatSkillIndex(item.currentVsPersistence)}`}
                  />
                )}
                <p className="text-13 text-ink-muted">{item.n === null ? '' : `${item.n.toLocaleString('en-IN')} forecasts in the latest window`}</p>
              </>
            )}
            <p className="mt-auto border-t border-line-soft pt-2.5 text-13 text-ink-2">{note}</p>
          </Card>
        )
      })}
    </section>
  )
}

import type { ForecastTarget, HorizonForecast } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { OUTCOME_TEXT } from '@/components/ui/outcomeClasses'
import { categoryOf, formatAqi } from '@/lib/aqi'
import { formatWhen } from '@/lib/format'
import { formatSkillMae, skillStatus } from '@/lib/skill'

const HORIZON_LABEL = { '1h': '+1 hour', '6h': '+6 hours', '24h': '+24 hours' } as const

interface HorizonCardsProps {
  horizons: readonly HorizonForecast[]
  target: ForecastTarget
  /** Timestamp of "now"; "15:00 today" is judged against it. */
  asOf: string
}

function detailFor(horizon: HorizonForecast, target: ForecastTarget, value: number): string {
  if (target === 'pm25') return 'µg/m³'
  const parts: string[] = [categoryOf(value).label]
  if (horizon.horizon === '1h') parts.push('close to now; AQI barely moves in an hour')
  else if (horizon.lo !== null && horizon.hi !== null) {
    parts.push(`likely ${formatAqi(horizon.lo)}–${formatAqi(horizon.hi)}`)
  }
  return parts.join(' · ')
}

/** One card per horizon. A withheld forecast says why instead of showing a number it cannot stand behind. */
export function HorizonCards({ horizons, target, asOf }: HorizonCardsProps) {
  return (
    <section aria-label="Forecast by horizon" className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
      {horizons.map((horizon) => {
        const status = skillStatus(horizon.backtestSkill)
        return (
          <Card key={horizon.horizon} className="flex flex-col gap-2.5 px-6 py-[22px]">
            <div className="flex items-baseline justify-between">
              <h2 className="font-semibold">{HORIZON_LABEL[horizon.horizon]}</h2>
              <p className="text-13 text-ink-muted">{formatWhen(horizon.validAt, asOf)}</p>
            </div>

            {horizon.value === null ? (
              <>
                <p className="font-mono text-40 leading-[1.1] text-ink-faint" aria-label="No forecast shown">
                  —
                </p>
                <p className="text-13 text-ink-2">Not shown: in backtests this model did not beat “same as now”.</p>
              </>
            ) : (
              <>
                <p className="font-mono text-40 leading-[1.1]">{formatAqi(horizon.value)}</p>
                <p className="text-13 text-ink-2">{detailFor(horizon, target, horizon.value)}</p>
              </>
            )}

            <div className="mt-auto flex justify-between gap-2 border-t border-line-soft pt-3 text-13">
              <span className="text-ink-muted">Backtest skill vs copy-last</span>
              <span className={`font-mono ${OUTCOME_TEXT[status]}`}>{formatSkillMae(horizon.backtestSkill)}</span>
            </div>
          </Card>
        )
      })}
    </section>
  )
}

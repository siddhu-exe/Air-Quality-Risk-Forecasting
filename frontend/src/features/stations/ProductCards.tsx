import type { Evidence, Forecast } from '@/api/schemas'
import { CategoryPill } from '@/components/aqi/CategoryPill'
import { Card } from '@/components/ui/Card'
import { OUTCOME_TEXT } from '@/components/ui/outcomeClasses'
import { formatAqi } from '@/lib/aqi'
import { formatWhen } from '@/lib/format'
import { evidenceFor, kindBadge, reasonLabel } from '@/lib/forecast'
import { formatSkillMae, skillStatus } from '@/lib/skill'

const HORIZON_LABEL = { '1h': '+1 hour', '6h': '+6 hours', '24h': '+24 hours' } as const

interface ProductCardsProps {
  forecasts: readonly Forecast[]
  /** Static backtest evidence for the skill line; the cards work without it. */
  evidence: readonly Evidence[] | undefined
  /** Timestamp of "now"; "15:00 today" is judged against it. */
  asOf: string
}

function Reference({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  if (value === null) return null
  return (
    <div className="flex justify-between gap-2">
      <span className="text-ink-muted">{label}</span>
      <span className="font-mono">
        {formatAqi(value)}
        {unit && <span className="text-ink-muted"> {unit}</span>}
      </span>
    </div>
  )
}

function Body({ forecast }: { forecast: Forecast }) {
  const unit = forecast.target === 'pm25' ? 'µg/m³' : ''
  if (forecast.status !== 'ok' || forecast.value === null) {
    const reason = forecast.reason ?? 'no forecast'
    return (
      <>
        <p className="font-mono text-40 leading-[1.1] text-ink-faint" aria-label="No forecast shown">
          —
        </p>
        <p className="text-14 font-medium text-ink-2">{forecast.status === 'withheld' ? 'Not published' : reasonLabel(reason)}</p>
        <p className="text-13 text-ink-2">{reason}</p>
      </>
    )
  }
  return (
    <>
      <p className="flex items-baseline gap-2 font-mono text-40 leading-[1.1]">
        {formatAqi(forecast.value)}
        {unit && <span className="text-14 text-ink-muted">{unit}</span>}
      </p>
      {forecast.category && (
        <p>
          <CategoryPill aqi={forecast.value} />
        </p>
      )}
      <div className="flex flex-col gap-1 border-t border-line-soft pt-2.5 text-13">
        <Reference label="Same as now" value={forecast.persistence} unit={unit} />
        {forecast.target === 'aqi' && forecast.product !== 'aqi_1h' && (
          <Reference label="24h-window update" value={forecast.windowUpdate} unit="" />
        )}
      </div>
    </>
  )
}

/**
 * One card per product. A forecast that does not exist says why instead of showing a number; the experimental 24h AQI
 * and the rule-based 1h AQI say so on the card and always show plain persistence beside the value.
 */
export function ProductCards({ forecasts, evidence, asOf }: ProductCardsProps) {
  return (
    <section aria-label="Forecast by horizon" className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
      {forecasts.map((forecast) => {
        const proof = evidence ? evidenceFor(evidence, forecast.product, 'test') : undefined
        return (
          <Card key={forecast.product} className="flex flex-col gap-2.5 px-6 py-[22px]">
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="font-semibold">{HORIZON_LABEL[forecast.horizon]}</h2>
              <p className="text-13 text-ink-muted">{forecast.validAt ? formatWhen(forecast.validAt, asOf) : ''}</p>
            </div>
            <p
              className={
                forecast.experimental
                  ? 'w-fit rounded bg-caution-bg px-2 py-0.5 text-12 text-caution-fg'
                  : 'w-fit rounded bg-wash px-2 py-0.5 text-12 text-ink-2'
              }
            >
              {kindBadge(forecast)}
              {forecast.experimental && ': about as accurate as assuming no change'}
              {forecast.kind === 'rule' && ': updates the 24-hour average'}
            </p>

            <Body forecast={forecast} />

            {proof && (
              <div className="mt-auto flex justify-between gap-2 border-t border-line-soft pt-3 text-13">
                <span className="text-ink-muted">Winter test skill vs same-as-now</span>
                <span className={`font-mono ${OUTCOME_TEXT[skillStatus(proof.skillVsPersistence)]}`}>
                  {formatSkillMae(proof.skillVsPersistence)}
                </span>
              </div>
            )}
          </Card>
        )
      })}
    </section>
  )
}

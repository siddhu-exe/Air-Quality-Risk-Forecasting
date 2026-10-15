import { Link } from 'react-router-dom'
import { useBacktest } from '@/api/queries'
import { describeError } from '@/api/describeError'
import type { Backtest, Evidence } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { formatPercent } from '@/lib/format'
import { evidenceFor } from '@/lib/forecast'

function Figure({ value, children }: { value: string; children: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-mono text-28">{value}</p>
      <p className="text-ink-2">{children}</p>
    </div>
  )
}

/** "smaller error than assuming nothing changes" as a signed percentage; a negative value reads as larger error. */
const skillText = (e: Evidence): string => `${e.skillVsPersistence >= 0 ? '' : '−'}${formatPercent(Math.abs(e.skillVsPersistence))}`

function TrustContent({ backtest }: { backtest: Backtest }) {
  const oneHour = evidenceFor(backtest.evidence, 'aqi_1h', 'test')
  const sixHour = evidenceFor(backtest.evidence, 'aqi_6h', 'test')
  const day = evidenceFor(backtest.evidence, 'aqi_24h', 'test')
  const dayReplay = evidenceFor(backtest.evidence, 'aqi_24h', 'replay')
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-6">
      {oneHour && (
        <Figure value={skillText(oneHour)}>
          smaller AQI error one hour ahead than assuming nothing changes, from a rule that updates the 24-hour average (winter test).
        </Figure>
      )}
      {sixHour && (
        <Figure value={skillText(sixHour)}>
          smaller AQI error six hours ahead for the model, and it also beats that rule (winter test).
        </Figure>
      )}
      {day && (
        <Figure value={skillText(day)}>
          {`for the experimental 24-hour AQI${
            dayReplay ? `; in the Sep–Oct 2026 replay it was ${skillText(dayReplay)}, about the same as assuming no change.` : '.'
          }`}
        </Figure>
      )}
    </div>
  )
}

/** "How far to trust this": backtest facts for each product and the not-an-advisory disclaimer. */
export function TrustStrip() {
  const { data, isPending, error } = useBacktest()

  return (
    <Card as="section" aria-labelledby="trust-title" className="hidden flex-col gap-5 px-8 py-7 md:flex">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="trust-title" className="font-serif text-30">
          How far to trust this
        </h2>
        <Link to="/model-health" className="link text-14">
          Live accuracy tracking
        </Link>
      </div>

      {data ? (
        <TrustContent backtest={data} />
      ) : isPending ? (
        <Skeleton className="h-24" />
      ) : (
        <p className="text-ink-2">Backtest figures are unavailable right now. {describeError(error)}</p>
      )}

      <p className="border-t border-line-soft pt-4 text-13 text-ink-muted">
        A statistical forecast from public CPCB station data, not an official advisory. For official forecasts see CPCB and SAFAR / IITM.
      </p>
    </Card>
  )
}

/** Phone footnote: the same disclaimer. */
export function TrustFootnote() {
  return (
    <p className="text-12 text-ink-muted md:hidden">
      Statistical forecast from CPCB station data, not an official advisory. The 24-hour AQI is experimental.
    </p>
  )
}

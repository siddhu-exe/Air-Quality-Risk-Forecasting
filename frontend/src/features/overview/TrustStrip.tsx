import { Link } from 'react-router-dom'
import { useBacktest } from '@/api/queries'
import { describeError } from '@/api/describeError'
import type { Backtest } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { formatPercent } from '@/lib/format'
import { countWord } from '@/lib/ranking'

function pastWinters(winters: number): string {
  return winters === 1 ? 'one past winter' : `${countWord(winters)} past winters`
}

function Figure({ value, children }: { value: string; children: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-mono text-28">{value}</p>
      <p className="text-ink-2">{children}</p>
    </div>
  )
}

function TrustContent({ backtest }: { backtest: Backtest }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-6">
      <Figure value={`~${formatPercent(backtest.skill24h)}`}>
        {`smaller 24h error than simply assuming tomorrow equals today, in ${pastWinters(backtest.winters)}.`}
      </Figure>
      <Figure value={formatPercent(backtest.coverage80)}>
        of winter days landed inside the 80% range. In bad spells, read the upper end.
      </Figure>
      <Figure value="24h">
        AQI is a 24-hour average, so it moves slowly and sudden spikes show up late.
      </Figure>
    </div>
  )
}

/** "How far to trust this": three backtest facts and the not-an-advisory disclaimer. */
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
        A statistical forecast from public CPCB station data, not an official advisory. For official forecasts
        see CPCB and SAFAR / IITM.
      </p>
    </Card>
  )
}

/** Phone footnote: the same disclaimer plus the headline accuracy figure. */
export function TrustFootnote() {
  const { data } = useBacktest()
  return (
    <p className="text-12 text-ink-muted md:hidden">
      Statistical forecast from CPCB station data, not an official advisory.
      {data && ` About ${formatPercent(data.skill24h)} smaller error than “tomorrow = today” in past winters.`}
    </p>
  )
}

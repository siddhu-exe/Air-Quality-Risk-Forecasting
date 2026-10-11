import { describeError } from '@/api/describeError'
import { useBacktest, useGrapAlerts } from '@/api/queries'
import type { GrapAlerts } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { Eyebrow } from '@/components/ui/Eyebrow'
import { Page } from '@/components/ui/Page'
import { Skeleton } from '@/components/ui/Skeleton'
import { StaleBanner } from '@/components/ui/StaleBanner'
import { SEVERE_THRESHOLD } from '@/lib/aqi'
import { countWord } from '@/lib/ranking'
import { AlertRule } from './AlertRule'
import { GrapStages } from './GrapStages'
import { LeadTimes } from './LeadTimes'
import { SevereAlerts } from './SevereAlerts'

const capitalise = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1)

/** One plain sentence: which stage is in force and how many stations are forecast to be Severe. */
function summarise({ stageInForce, stages }: GrapAlerts): string {
  const stage = stageInForce ? `Stage ${stageInForce} is in force.` : 'No GRAP stage is in force.'
  const severeTomorrow = stages.filter((s) => s.min >= SEVERE_THRESHOLD).reduce((sum, s) => sum + s.tomorrowCount, 0)
  const outlook =
    severeTomorrow === 0
      ? 'No station is forecast to reach Severe within 24 hours.'
      : `${capitalise(countWord(severeTomorrow))} ${severeTomorrow === 1 ? 'station is' : 'stations are'} forecast to reach Severe within 24 hours.`
  return `${stage} ${outlook}`
}

/** The page for city and pollution-control staff: stages, alerts, and how good the alert rules are. */
export function OperationsPage() {
  const alerts = useGrapAlerts()
  const backtest = useBacktest()

  if (alerts.isPending) {
    return (
      <Page>
        <span className="sr-only" role="status">
          Loading the GRAP outlook
        </span>
        <Skeleton className="h-16 w-80" />
        <Skeleton className="h-44 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </Page>
    )
  }
  if (alerts.error) {
    return (
      <Page>
        <ErrorState message={describeError(alerts.error)} onRetry={() => void alerts.refetch()} />
      </Page>
    )
  }

  const data = alerts.data
  return (
    <Page>
      {data.stale && <StaleBanner dataAsOf={data.dataAsOf} />}

      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>For city and pollution-control staff</Eyebrow>
          <h1 className="mt-1 font-serif text-40 leading-none md:text-56">GRAP outlook</h1>
        </div>
        <p className="max-w-[460px] text-ink-2">{summarise(data)}</p>
      </section>

      <GrapStages stages={data.stages} stageInForce={data.stageInForce} />
      <SevereAlerts data={data} />

      <div className="flex flex-wrap gap-4 md:gap-6">
        {backtest.data ? (
          <>
            <AlertRule backtest={backtest.data} />
            <LeadTimes leadTimes={backtest.data.leadTimes} />
          </>
        ) : backtest.isPending ? (
          <Skeleton className="h-72 w-full rounded-2xl" />
        ) : (
          <Card className="w-full p-6">
            <p className="text-ink-2">Backtest figures are unavailable right now. {describeError(backtest.error)}</p>
          </Card>
        )}
      </div>
    </Page>
  )
}

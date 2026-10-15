import { describeError } from '@/api/describeError'
import { useBacktest, useGrapAlerts } from '@/api/queries'
import type { GrapAlerts } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { Eyebrow } from '@/components/ui/Eyebrow'
import { Page } from '@/components/ui/Page'
import { Skeleton } from '@/components/ui/Skeleton'
import { StaleBanner } from '@/components/ui/StaleBanner'
import { formatAqi } from '@/lib/aqi'
import { countWord } from '@/lib/ranking'
import { EvidenceTable } from './EvidenceTable'
import { GrapStages } from './GrapStages'
import { GrapStations } from './GrapStations'

const capitalise = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1)

/** One plain sentence: which stage today's readings indicate and how many stations are forecast Severe in six hours. */
function summarise({ stageIndicatedNow, networkMeanAqiNow, stages }: GrapAlerts): string {
  if (networkMeanAqiNow === null) return 'No station has a recent reading, so no stage can be indicated.'
  const stage = stageIndicatedNow
    ? `The city mean of ${formatAqi(networkMeanAqiNow)} indicates Stage ${stageIndicatedNow}.`
    : `The city mean of ${formatAqi(networkMeanAqiNow)} is below Stage I.`
  const severe = stages.filter((s) => s.min >= 401).reduce((sum, s) => sum + s.forecast6hCount, 0)
  const outlook =
    severe === 0
      ? 'No station is forecast to reach Severe within six hours.'
      : `${capitalise(countWord(severe))} ${severe === 1 ? 'station is' : 'stations are'} forecast to reach Severe within six hours.`
  return `${stage} ${outlook}`
}

/** The page for city and pollution-control staff: indicative stages, each station against the bands, and the evidence. */
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

      <p className="rounded-xl bg-caution-bg px-4 py-3 text-14 text-caution-fg">{data.disclaimer}</p>

      <GrapStages stages={data.stages} stageIndicated={data.stageIndicatedNow} />
      <GrapStations stations={data.stations} />

      {backtest.data ? (
        <EvidenceTable backtest={backtest.data} />
      ) : backtest.isPending ? (
        <Skeleton className="h-72 w-full rounded-2xl" />
      ) : (
        <Card className="w-full p-6">
          <p className="text-ink-2">Backtest figures are unavailable right now. {describeError(backtest.error)}</p>
        </Card>
      )}
    </Page>
  )
}

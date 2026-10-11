import { describeError } from '@/api/describeError'
import { useOverview } from '@/api/queries'
import { ErrorState } from '@/components/ui/ErrorState'
import { Page } from '@/components/ui/Page'
import { StaleBanner } from '@/components/ui/StaleBanner'
import { AdvicePanel } from './AdvicePanel'
import { CityHero } from './CityHero'
import { OverviewSkeleton } from './OverviewSkeleton'
import { StationMap } from './StationMap'
import { StationList, StationTable } from './StationTable'
import { TrustFootnote, TrustStrip } from './TrustStrip'

/** Tomorrow's city forecast, what to do about it, and how each station compares. */
export function OverviewPage() {
  const { data, isPending, error, refetch } = useOverview()

  if (isPending) return <OverviewSkeleton />
  if (error) {
    return (
      <Page>
        <ErrorState message={describeError(error)} onRetry={() => void refetch()} />
      </Page>
    )
  }

  return (
    <Page className="md:gap-7 md:pt-10">
      {data.stale && <StaleBanner dataAsOf={data.dataAsOf} />}

      <div className="flex flex-wrap gap-4 md:gap-6">
        <CityHero overview={data} />
        <AdvicePanel forecast24h={data.network.forecast24h} grapStageInForce={data.grapStageInForce} />
      </div>

      <div className="flex flex-wrap gap-4 md:gap-6">
        <StationMap stations={data.stations} />
        <StationTable stations={data.stations} />
        <StationList stations={data.stations} />
      </div>

      <TrustStrip />
      <TrustFootnote />
    </Page>
  )
}

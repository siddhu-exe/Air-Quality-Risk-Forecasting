import { describeError } from '@/api/describeError'
import { useBacktest, useModelHealth } from '@/api/queries'
import { ErrorState } from '@/components/ui/ErrorState'
import { Eyebrow } from '@/components/ui/Eyebrow'
import { Page } from '@/components/ui/Page'
import { Skeleton } from '@/components/ui/Skeleton'
import { StaleBanner } from '@/components/ui/StaleBanner'
import { CalibrationCards } from './CalibrationCards'
import { FreshnessTable } from './FreshnessTable'
import { JobsList, ModelsList } from './JobsAndModels'
import { SkillCards } from './SkillCards'

/** Is the forecast still beating "same as now"? Skill, calibration, data freshness and jobs. */
export function ModelHealthPage() {
  const health = useModelHealth()
  const backtest = useBacktest()

  if (health.isPending) {
    return (
      <Page>
        <span className="sr-only" role="status">
          Loading model health
        </span>
        <Skeleton className="h-16 w-80" />
        <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-72 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-40 rounded-2xl" />
      </Page>
    )
  }
  if (health.error) {
    return (
      <Page>
        <ErrorState message={describeError(health.error)} onRetry={() => void health.refetch()} />
      </Page>
    )
  }

  const data = health.data
  return (
    <Page>
      {data.stale && <StaleBanner dataAsOf={data.dataAsOf} />}

      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Is the forecast still earning its keep?</Eyebrow>
          <h1 className="mt-1 font-serif text-40 leading-none md:text-56">Model health</h1>
        </div>
        <p className="max-w-[520px] text-ink-2">
          Every forecast is scored against what actually happened and against copy-last-value. Skill = 1 − model
          error ÷ copy-last error. Below 0 means the model is losing.
        </p>
      </section>

      <SkillCards skill={data.skill} />
      <CalibrationCards calibration={data.calibration} backtest={backtest.data} />

      <div className="flex flex-wrap gap-4 md:gap-6">
        <FreshnessTable rows={data.freshness} generatedAt={data.generatedAt} />
        <div className="flex min-w-0 flex-[1_1_360px] flex-col gap-4 md:gap-6">
          <JobsList jobs={data.jobs} />
          <ModelsList models={data.models} />
        </div>
      </div>
    </Page>
  )
}

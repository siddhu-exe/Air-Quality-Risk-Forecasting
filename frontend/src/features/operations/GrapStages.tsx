import type { GrapAlerts } from '@/api/schemas'
import { cn } from '@/lib/cn'

type Stage = GrapAlerts['stages'][number]

function rangeLabel(stage: Stage): string {
  return stage.max === null ? `AQI above ${stage.min - 1}` : `AQI ${stage.min}–${stage.max}`
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-12 opacity-80">{label}</p>
      <p className="font-mono text-26">{value}</p>
    </div>
  )
}

interface GrapStagesProps {
  stages: GrapAlerts['stages']
  stageIndicated: GrapAlerts['stageIndicatedNow']
}

/** The four GRAP stages, how many stations sit in each now and in six hours, and which stage today's mean indicates. */
export function GrapStages({ stages, stageIndicated }: GrapStagesProps) {
  return (
    <section aria-label="GRAP stages" className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
      {stages.map((stage) => {
        const active = stage.stage === stageIndicated
        return (
          <div
            key={stage.stage}
            className={cn(
              'flex flex-col gap-3.5 rounded-2xl border px-[22px] py-5',
              active ? 'border-grap-bg bg-grap-bg text-white' : 'border-line bg-surface text-ink',
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">Stage {stage.stage}</h2>
              {active && (
                <span className="rounded-full bg-surface px-2.5 py-0.5 text-12 font-medium text-ink">Indicated now</span>
              )}
            </div>
            <div>
              <p className="text-13 opacity-80">{rangeLabel(stage)}</p>
              <p className="text-14">{stage.label}</p>
            </div>
            <div className={cn('grid grid-cols-2 gap-2 border-t pt-3', active ? 'border-grap-rule' : 'border-line-soft')}>
              <Count label="Stations now" value={stage.nowCount} />
              <Count label="In 6 hours" value={stage.forecast6hCount} />
            </div>
          </div>
        )
      })}
    </section>
  )
}

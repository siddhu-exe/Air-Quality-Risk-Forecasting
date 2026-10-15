import type { ModelHealth } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatClock, formatDay } from '@/lib/format'

const JOB_NAME: Record<string, { name: string; schedule: string }> = {
  ingest: { name: 'Ingest readings', schedule: 'Hourly at :10' },
  forecast: { name: 'Issue forecasts', schedule: 'Not scheduled until a source is fresh' },
  score: { name: 'Score vs actuals', schedule: 'Manual for now' },
  shadow: { name: 'WAQI shadow ingest', schedule: 'Hourly at :20; never used for forecasts' },
  backfill: { name: 'Backfill history', schedule: 'Manual' },
}

const STATUS: Record<string, { label: string; dot: string }> = {
  success: { label: 'OK', dot: 'bg-aqi-good' },
  partial: { label: 'Partial', dot: 'bg-aqi-poor' },
  running: { label: 'Running', dot: 'bg-aqi-satisfactory' },
  failed: { label: 'Failed', dot: 'bg-aqi-very-poor' },
}

/** Jobs and their last status; the status word carries the meaning, the dot only reinforces it. */
export function JobsList({ jobs }: { jobs: ModelHealth['jobs'] }) {
  return (
    <Card as="section" aria-labelledby="jobs-title" className="flex flex-col px-5 py-6 md:px-7">
      <h2 id="jobs-title" className="mb-2 text-17 font-semibold">
        Jobs
      </h2>
      {jobs.length === 0 ? (
        <p className="text-ink-2">No job has run yet.</p>
      ) : (
        <ul>
          {jobs.map((job) => {
            const status = STATUS[job.status] ?? { label: job.status, dot: 'bg-line-strong' }
            const info = JOB_NAME[job.job] ?? { name: job.job, schedule: '' }
            return (
              <li key={job.job} className="grid grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-3 border-t border-line-soft py-3">
                <span aria-hidden="true" className={`h-2 w-2 rounded-full ${status.dot}`} />
                <span>
                  <span className="font-medium">{info.name}</span>
                  <br />
                  <span className="text-13 text-ink-muted">{info.schedule}</span>
                </span>
                <span className="text-right font-mono text-13 text-ink-2">
                  {status.label}
                  {job.lastRunAt && ` · ${formatClock(job.lastRunAt)} ${formatDay(job.lastRunAt)}`}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

export function ModelsList({ models }: { models: ModelHealth['models'] }) {
  return (
    <Card as="section" aria-labelledby="models-title" className="flex flex-col px-5 py-6 md:px-7">
      <h2 id="models-title" className="mb-2 text-17 font-semibold">
        In service
      </h2>
      <ul>
        {models.map((model) => (
          <li key={model.version} className="flex items-baseline justify-between gap-3 border-t border-line-soft py-3">
            <span>
              <span className="font-medium">{model.name}</span>
              <br />
              <span className="text-13 text-ink-muted">
                {model.target === 'aqi' ? 'AQI' : 'PM2.5'} · {model.horizon} · {model.sha256.slice(0, 8)}
              </span>
            </span>
            <span className="whitespace-nowrap rounded-md bg-wash px-2 py-0.5 font-mono text-12">{model.version}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

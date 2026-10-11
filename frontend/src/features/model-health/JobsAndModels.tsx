import type { ModelHealth } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatClock } from '@/lib/format'

type JobStatus = ModelHealth['jobs'][number]['status']

const JOB_STATUS: Record<JobStatus, { label: string; dot: string }> = {
  ok: { label: 'OK', dot: 'bg-aqi-good' },
  retry: { label: 'Retry', dot: 'bg-aqi-poor' },
  failed: { label: 'Failed', dot: 'bg-aqi-very-poor' },
}

/** Scheduled jobs; the status word carries the meaning, the dot only reinforces it. */
export function JobsList({ jobs }: { jobs: ModelHealth['jobs'] }) {
  return (
    <Card as="section" aria-labelledby="jobs-title" className="flex flex-col px-7 py-6">
      <h2 id="jobs-title" className="mb-2 text-17 font-semibold">
        Scheduled jobs
      </h2>
      <ul>
        {jobs.map((job) => {
          const status = JOB_STATUS[job.status]
          return (
            <li key={job.id} className="grid grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-3 border-t border-line-soft py-3">
              <span aria-hidden="true" className={`h-2 w-2 rounded-full ${status.dot}`} />
              <span>
                <span className="font-medium">{job.name}</span>
                <br />
                <span className="text-13 text-ink-muted">{job.schedule}</span>
              </span>
              <span className="text-right font-mono text-13 text-ink-2">
                {status.label} · {formatClock(job.lastRunAt)}
              </span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

export function ModelsList({ models }: { models: ModelHealth['models'] }) {
  return (
    <Card as="section" aria-labelledby="models-title" className="flex flex-col px-7 py-6">
      <h2 id="models-title" className="mb-2 text-17 font-semibold">
        Models in service
      </h2>
      <ul>
        {models.map((model) => (
          <li key={model.name} className="flex items-baseline justify-between gap-3 border-t border-line-soft py-3">
            <span>
              <span className="font-medium">{model.name}</span>
              <br />
              <span className="text-13 text-ink-muted">{model.description}</span>
            </span>
            <span className="whitespace-nowrap rounded-md bg-wash px-2 py-0.5 font-mono text-12">{model.version}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

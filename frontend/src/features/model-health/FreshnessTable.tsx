import type { ModelHealth } from '@/api/schemas'
import { FreshnessStrip } from '@/components/charts/FreshnessStrip'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/cn'
import { formatAge, msBetween } from '@/lib/format'

/** A reading older than this is shown in the "late" colour. */
const LATE_AFTER_MS = 60 * 60 * 1000

interface FreshnessTableProps {
  rows: ModelHealth['freshness']
  /** Server clock; ages are measured against it, not the browser's. */
  generatedAt: string
}

export function FreshnessTable({ rows, generatedAt }: FreshnessTableProps) {
  return (
    <Card as="section" aria-labelledby="freshness-title" className="min-w-0 flex-[999_1_560px] px-5 py-6 md:px-7">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="freshness-title" className="text-17 font-semibold">
          Data freshness
        </h2>
        <span className="text-13 text-ink-muted">Hourly ingest from OpenAQ (CPCB stations)</span>
      </div>
      <ul className="flex flex-col md:hidden">
        {rows.map((row) => {
          const age = row.lastReadingAt === null ? null : msBetween(generatedAt, row.lastReadingAt)
          const late = age === null || age >= LATE_AFTER_MS
          return (
            <li key={row.stationId} className="flex flex-col gap-2 border-t border-line-soft py-3.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-15 font-medium">{row.name}</span>
                <span className={cn('font-mono text-14', late ? 'text-fresh-late' : 'text-ink-2')}>
                  {age === null ? 'no reading' : formatAge(age)}
                  {late && <span className="sr-only"> (late)</span>}
                </span>
              </div>
              <FreshnessStrip hourly={row.hourly} />
              {row.note && <p className="text-13 text-ink-2">{row.note}</p>}
            </li>
          )
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[560px] border-collapse text-14">
          <thead>
            <tr className="text-left text-13 text-ink-muted">
              <th scope="col" className="py-2.5 pr-3 font-medium">Station</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Last reading</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Last 24 hours</th>
              <th scope="col" className="py-2.5 pl-3 font-medium">Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const age = row.lastReadingAt === null ? null : msBetween(generatedAt, row.lastReadingAt)
              const late = age === null || age >= LATE_AFTER_MS
              return (
                <tr key={row.stationId} className="border-t border-line-soft">
                  <th scope="row" className="py-3 pr-3 text-left font-medium">{row.name}</th>
                  <td className={cn('px-3 py-3 font-mono', late ? 'text-fresh-late' : 'text-ink-2')}>
                    {age === null ? 'no reading' : formatAge(age)}
                    {late && <span className="sr-only"> (late)</span>}
                  </td>
                  <td className="px-3 py-3">
                    <FreshnessStrip hourly={row.hourly} />
                  </td>
                  <td className="py-3 pl-3 text-13 text-ink-2">{row.note}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

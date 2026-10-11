import { Link } from 'react-router-dom'
import type { OverviewStation } from '@/api/schemas'
import { CategoryPill } from '@/components/aqi/CategoryPill'
import { TIER_FILL } from '@/components/aqi/tierClasses'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { categoryOf, formatAqi } from '@/lib/aqi'
import { formatPercent } from '@/lib/format'
import { rankByForecast } from '@/lib/ranking'

interface StationListProps {
  stations: readonly OverviewStation[]
}

function rowLabel(station: OverviewStation): string {
  return `${station.name}: AQI ${formatAqi(station.now)} now, ${formatAqi(station.forecast24h)} tomorrow, ${
    categoryOf(station.forecast24h).label
  }, ${formatPercent(station.pSevere)} chance of Severe`
}

/** Desktop: worst station first, with now, forecast, category and chance of Severe. */
export function StationTable({ stations }: StationListProps) {
  return (
    <Card as="section" aria-labelledby="table-title" className="hidden min-w-0 flex-[1_1_520px] flex-col gap-1 p-6 md:flex">
      <div className="flex flex-wrap items-baseline justify-between gap-3 pb-3">
        <h2 id="table-title" className="text-17 font-semibold">
          Tomorrow by station
        </h2>
        <span className="text-13 text-ink-muted">Now → 24h forecast · chance of Severe</span>
      </div>
      <ul>
        {rankByForecast(stations).map((station) => (
          <li key={station.id}>
            <Link
              to={`/stations/${station.id}`}
              aria-label={rowLabel(station)}
              className="grid min-h-[60px] grid-cols-[minmax(0,1.6fr)_48px_20px_52px_minmax(0,1fr)_minmax(0,1.1fr)] items-center gap-3 rounded-lg border-t border-line-soft px-2 text-ink no-underline hover:bg-page"
            >
              <span className="truncate font-medium">{station.name}</span>
              <span className="text-right font-mono text-ink-muted">{formatAqi(station.now)}</span>
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M3 8h9M9 4l4 4-4 4"
                  fill="none"
                  className="stroke-ink-subtle"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span className="font-mono font-medium">{formatAqi(station.forecast24h)}</span>
              <CategoryPill aqi={station.forecast24h} className="justify-self-start" />
              <span className="flex items-center gap-2">
                <ProgressBar value={station.pSevere} fillClassName="h-full bg-aqi-severe" className="flex-1" />
                <span className="w-9 text-right font-mono text-13">{formatPercent(station.pSevere)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** Phone: one compact row per station, dot coloured by tomorrow's category. */
export function StationList({ stations }: StationListProps) {
  return (
    <Card as="section" aria-labelledby="list-title" className="w-full px-[18px] py-2 md:hidden">
      <h2 id="list-title" className="mb-1 mt-3 text-16 font-semibold">
        Tomorrow by station
      </h2>
      <ul>
        {rankByForecast(stations).map((station) => (
          <li key={station.id}>
            <Link
              to={`/stations/${station.id}`}
              aria-label={rowLabel(station)}
              className="grid min-h-14 grid-cols-[10px_minmax(0,1fr)_auto_auto] items-center gap-3 border-t border-line-soft text-ink no-underline"
            >
              <span
                aria-hidden="true"
                className={`h-2.5 w-2.5 rounded-full ${TIER_FILL[categoryOf(station.forecast24h).key]}`}
              />
              <span className="font-medium">{station.name}</span>
              <span className="font-mono text-13 text-ink-muted">{formatAqi(station.now)} →</span>
              <span className="w-9 text-right font-mono font-medium">{formatAqi(station.forecast24h)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}

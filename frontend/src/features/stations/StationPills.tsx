import { Link } from 'react-router-dom'
import type { StationSummary } from '@/api/schemas'
import { TIER_FILL } from '@/components/aqi/tierClasses'
import { categoryOf } from '@/lib/aqi'
import { cn } from '@/lib/cn'

interface StationPillsProps {
  stations: readonly StationSummary[]
  selectedId: string
}

/**
 * Real links, so a station has its own URL and the back button works. The
 * dot shows AQI now; the current station is marked with aria-current.
 */
export function StationPills({ stations, selectedId }: StationPillsProps) {
  return (
    <nav aria-label="Choose a station" className="flex flex-wrap gap-2">
      {stations.map((station) => {
        const selected = station.id === selectedId
        return (
          <Link
            key={station.id}
            to={`/stations/${station.id}`}
            aria-current={selected ? 'true' : undefined}
            className={cn(
              'inline-flex min-h-target items-center gap-2 rounded-full border px-4 text-14 no-underline',
              selected
                ? 'border-ink bg-ink text-white'
                : 'border-line-strong bg-surface text-ink hover:bg-wash',
            )}
          >
            <span
              aria-hidden="true"
              className={cn('h-2 w-2 rounded-full', station.aqiNow === null ? 'bg-line-strong' : TIER_FILL[categoryOf(station.aqiNow).key])}
            />
            {station.name}
          </Link>
        )
      })}
    </nav>
  )
}

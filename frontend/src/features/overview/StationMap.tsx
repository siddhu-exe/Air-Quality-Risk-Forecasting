import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import type { OverviewStation } from '@/api/schemas'
import { TIER_FILL, TIER_SOLID } from '@/components/aqi/tierClasses'
import { Card } from '@/components/ui/Card'
import { AQI_CATEGORIES, categoryOf, categoryRange, formatAqi } from '@/lib/aqi'
import { DELHI_MAP_BOX, projectToMap } from '@/lib/projection'

interface StationMapProps {
  stations: readonly OverviewStation[]
}

/** "6 Very Poor, 1 Severe": a text twin of what the dots show. */
function summarise(stations: readonly OverviewStation[]): string {
  const counts = new Map<string, number>()
  for (const station of stations) {
    const label = categoryOf(station.now).label
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  return [...counts].map(([label, n]) => `${n} ${label}`).join(', ')
}

/**
 * Stylised outline of Delhi with one pin per station, coloured by AQI now.
 * Pins are real coordinates fitted into the artwork (lib/projection.ts), not
 * a geographic map: the outline and river are illustrations.
 */
export function StationMap({ stations }: StationMapProps) {
  const positions = useMemo(() => projectToMap(stations), [stations])
  const present = new Set(stations.map((s) => categoryOf(s.now).key))
  // Moderate and worse are always listed; cleaner bands appear only when a pin uses them.
  const legend = AQI_CATEGORIES.filter((c) => c.min >= 101 || present.has(c.key))

  return (
    <Card as="section" aria-labelledby="map-title" className="hidden min-w-0 flex-[1_1_560px] flex-col gap-4 p-6 md:flex">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="map-title" className="text-17 font-semibold">
          Stations now
        </h2>
        <span className="text-13 text-ink-muted">{stations.length} CAAQMS monitors</span>
      </div>

      <div
        role="group"
        aria-label={`Map of Delhi with ${stations.length} monitoring stations: ${summarise(stations)}`}
        className="relative mx-auto w-full max-w-[600px] overflow-hidden rounded-xl bg-wash"
        style={{ height: DELHI_MAP_BOX.height }}
      >
        <svg
          viewBox={`0 0 ${DELHI_MAP_BOX.width} ${DELHI_MAP_BOX.height}`}
          preserveAspectRatio="none"
          aria-hidden="true"
          className="absolute inset-0 h-full w-full"
        >
          <path
            d="M70 40 C 180 10, 420 20, 520 90 C 590 150, 580 330, 500 410 C 420 470, 230 470, 140 420 C 50 370, 20 240, 30 160 C 36 100, 50 60, 70 40 Z"
            className="fill-map-land stroke-map-outline"
            strokeWidth="1.5"
          />
          <path
            d="M360 0 C 380 80, 420 140, 410 220 C 400 290, 440 340, 470 480"
            fill="none"
            className="stroke-map-river"
            strokeWidth="6"
            strokeLinecap="round"
          />
        </svg>

        {stations.map((station, index) => {
          const position = positions[index]
          if (!position) return null
          const category = categoryOf(station.now)
          return (
            <Link
              key={station.id}
              to={`/stations/${station.id}`}
              aria-label={`${station.name}: AQI ${formatAqi(station.now)} now, ${category.label}`}
              className="absolute flex min-h-target min-w-target -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 text-ink no-underline"
              style={{ left: `${position.leftPct}%`, top: position.topPx }}
            >
              <span
                className={`flex h-[46px] w-[46px] items-center justify-center rounded-full font-mono text-14 font-medium ring-4 ring-surface ${TIER_SOLID[category.key]}`}
              >
                {formatAqi(station.now)}
              </span>
              <span className="whitespace-nowrap rounded bg-surface px-1.5 py-px text-12 font-medium">
                {station.name}
              </span>
            </Link>
          )
        })}

        <span
          aria-hidden="true"
          className="absolute left-[430px] top-[440px] text-11 italic text-map-riverLabel"
        >
          Yamuna
        </span>
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-2 text-12 text-ink-muted" aria-label="Colour key">
        {legend.map((category) => (
          <li key={category.key} className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${TIER_FILL[category.key]}`} />
            {category.label} {categoryRange(category)}
          </li>
        ))}
      </ul>
    </Card>
  )
}

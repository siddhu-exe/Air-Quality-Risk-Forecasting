import type { StationSummary } from '@/api/schemas'
import { CategoryPill } from '@/components/aqi/CategoryPill'
import { Eyebrow } from '@/components/ui/Eyebrow'
import { formatAqi } from '@/lib/aqi'

/** Station name with the two numbers people ask for first: AQI and PM2.5 right now. */
export function StationHeader({ station }: { station: StationSummary }) {
  return (
    <section className="flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
      <div className="flex flex-col gap-1.5">
        <Eyebrow>CAAQMS station · {station.area}</Eyebrow>
        <h1 className="font-serif text-40 leading-none md:text-64">{station.name}</h1>
      </div>
      <div className="flex flex-wrap gap-8">
        <div>
          <p className="text-13 text-ink-muted">AQI now</p>
          <p className="flex items-center gap-2.5">
            <span className="font-mono text-36">{formatAqi(station.aqiNow)}</span>
            <CategoryPill aqi={station.aqiNow} />
          </p>
        </div>
        <div>
          <p className="text-13 text-ink-muted">PM2.5 now</p>
          <p className="font-mono text-36">
            {station.pm25Now === null ? '—' : formatAqi(station.pm25Now)}
            {station.pm25Now !== null && <span className="text-14 text-ink-muted"> µg/m³</span>}
          </p>
        </div>
      </div>
    </section>
  )
}

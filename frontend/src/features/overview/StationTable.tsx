import { Link } from 'react-router-dom'
import type { OverviewStation, ProductKey } from '@/api/schemas'
import { CategoryPill } from '@/components/aqi/CategoryPill'
import { TIER_FILL } from '@/components/aqi/tierClasses'
import { ForecastCell } from '@/components/forecast/ForecastCell'
import { Card } from '@/components/ui/Card'
import { categoryOf, formatAqi } from '@/lib/aqi'
import { findForecast, rankByNow } from '@/lib/forecast'

interface StationListProps {
  stations: readonly OverviewStation[]
}

const COLUMNS: { product: ProductKey; head: string; sub: string; unit?: string }[] = [
  { product: 'pm25_1h', head: 'PM2.5 +1h', sub: 'model', unit: 'µg/m³' },
  { product: 'pm25_6h', head: 'PM2.5 +6h', sub: 'model', unit: 'µg/m³' },
  { product: 'aqi_1h', head: 'AQI +1h', sub: 'rule-based' },
  { product: 'aqi_6h', head: 'AQI +6h', sub: 'model' },
  { product: 'aqi_24h', head: 'AQI +24h', sub: 'experimental' },
]

function rowLabel(station: OverviewStation): string {
  const now = station.now
    ? `AQI ${formatAqi(station.now.value)} now${station.now.stale ? ' (old reading)' : ''}`
    : 'no current reading'
  const six = findForecast(station.forecasts, 'aqi_6h')
  const ahead = six?.status === 'ok' && six.value !== null ? `, ${formatAqi(six.value)} in 6 hours` : ', no 6-hour forecast'
  return `${station.name}: ${now}${ahead}`
}

function NowCell({ station }: { station: OverviewStation }) {
  if (!station.now) return <span className="text-13 text-ink-muted">— no reading</span>
  return (
    <span className="flex flex-col items-start gap-0.5">
      <span className="flex items-center gap-2">
        <span className="font-mono font-medium">{formatAqi(station.now.value)}</span>
        <CategoryPill aqi={station.now.value} />
      </span>
      {station.now.stale && <span className="text-12 text-ink-muted">old reading</span>}
    </span>
  )
}

/** Desktop: worst station first. Each forecast cell is a value or the reason there is none. */
export function StationTable({ stations }: StationListProps) {
  return (
    <Card as="section" aria-labelledby="table-title" className="hidden min-w-0 flex-[1_1_620px] flex-col gap-1 p-6 md:flex">
      <div className="flex flex-wrap items-baseline justify-between gap-3 pb-3">
        <h2 id="table-title" className="text-17 font-semibold">
          Forecast by station
        </h2>
        <span className="text-13 text-ink-muted">Worst now first · a dash gives the reason</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-14">
          <thead>
            <tr className="text-left text-13 text-ink-muted">
              <th scope="col" className="py-2 pr-3 font-medium">
                Station
              </th>
              <th scope="col" className="px-2 py-2 font-medium">
                AQI now
              </th>
              {COLUMNS.map((c) => (
                <th key={c.product} scope="col" className="px-2 py-2 font-medium">
                  {c.head}
                  <span className="block text-12 font-normal">{c.sub}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rankByNow(stations).map((station) => (
              <tr key={station.id} className="border-t border-line-soft align-top">
                <th scope="row" className="py-3 pr-3 text-left font-medium">
                  <Link to={`/stations/${station.id}`} aria-label={rowLabel(station)} className="text-ink">
                    {station.name}
                  </Link>
                </th>
                <td className="px-2 py-3">
                  <NowCell station={station} />
                </td>
                {COLUMNS.map((c) => (
                  <td key={c.product} className="px-2 py-3">
                    <ForecastCell forecast={findForecast(station.forecasts, c.product)} unit={c.unit} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="pt-3 text-12 text-ink-muted">
        AQI +1h is a rule, not a model: it recomputes the 24-hour average assuming the next hour stays as the current one.
        AQI +24h is experimental and shown with “same as now”.
      </p>
    </Card>
  )
}

/** Phone: one compact entry per station with the two headline forecasts, or why there are none. */
export function StationList({ stations }: StationListProps) {
  return (
    <Card as="section" aria-labelledby="list-title" className="w-full px-[18px] py-2 md:hidden">
      <h2 id="list-title" className="mb-1 mt-3 text-16 font-semibold">
        Forecast by station
      </h2>
      <ul>
        {rankByNow(stations).map((station) => (
          <li key={station.id} className="border-t border-line-soft py-3">
            <Link to={`/stations/${station.id}`} aria-label={rowLabel(station)} className="flex flex-col gap-1.5 text-ink no-underline">
              <span className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className={`h-2.5 w-2.5 rounded-full ${station.now ? TIER_FILL[categoryOf(station.now.value).key] : 'bg-line-strong'}`}
                />
                <span className="flex-1 font-medium">{station.name}</span>
                <span className="font-mono text-13 text-ink-muted">
                  {station.now ? `${formatAqi(station.now.value)} now` : 'no reading'}
                </span>
              </span>
              <span className="grid grid-cols-2 gap-3 pl-[22px] text-13">
                <span>
                  <span className="block text-12 text-ink-muted">PM2.5 +6h</span>
                  <ForecastCell forecast={findForecast(station.forecasts, 'pm25_6h')} unit="µg/m³" />
                </span>
                <span>
                  <span className="block text-12 text-ink-muted">AQI +6h</span>
                  <ForecastCell forecast={findForecast(station.forecasts, 'aqi_6h')} />
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}

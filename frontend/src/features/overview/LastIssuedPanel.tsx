import type { OverviewStation, ProductKey } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { Eyebrow } from '@/components/ui/Eyebrow'
import { formatAqi } from '@/lib/aqi'
import { formatClock, formatDay } from '@/lib/format'
import { lastIssued, newestIssue } from '@/lib/forecast'

/** "Wed 7 Oct 19:00": a past time always carries its date. */
const when = (iso: string): string => `${formatDay(iso)} ${formatClock(iso)}`

const COLUMNS: { product: ProductKey; head: string; unit?: string }[] = [
  { product: 'pm25_1h', head: 'PM2.5 +1h', unit: 'µg/m³' },
  { product: 'pm25_6h', head: 'PM2.5 +6h', unit: 'µg/m³' },
  { product: 'aqi_1h', head: 'AQI +1h' },
  { product: 'aqi_6h', head: 'AQI +6h' },
  { product: 'aqi_24h', head: 'AQI +24h' },
]

/**
 * The last forecast that was issued, shown while there is no current one. It is history: every value carries the time it
 * was issued and the time it predicted, and the card says in words that it is not a forecast for now.
 */
export function LastIssuedPanel({ stations }: { stations: readonly OverviewStation[] }) {
  const newest = newestIssue(stations)
  return (
    <Card as="section" aria-labelledby="last-issued-title" className="flex min-w-0 flex-[1_1_100%] flex-col gap-3 p-6">
      <div className="flex flex-col gap-1">
        <Eyebrow>Past · not a forecast for now</Eyebrow>
        <h2 id="last-issued-title" className="text-17 font-semibold">
          Last forecast issued
        </h2>
      </div>
      {newest === null ? (
        <p className="text-14 text-ink-2">No forecast has been issued yet.</p>
      ) : (
        <>
          <p className="text-14 text-ink-2">
            Issued {formatClock(newest)} IST on {formatDay(newest)}. These values predicted the times shown under each one
            and are kept here as history only; they say nothing about the air now.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-14">
              <caption className="sr-only">The last forecast issued for each station, with the time it predicted</caption>
              <thead>
                <tr className="text-left text-13 text-ink-muted">
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Station
                  </th>
                  {COLUMNS.map((c) => (
                    <th key={c.product} scope="col" className="px-2 py-2 font-medium">
                      {c.head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stations.map((station) => (
                  <tr key={station.id} className="border-t border-line-soft align-top">
                    <th scope="row" className="py-3 pr-3 text-left font-medium">
                      {station.name}
                    </th>
                    {COLUMNS.map((c) => {
                      const past = lastIssued(station.forecasts, c.product)
                      return (
                        <td key={c.product} className="px-2 py-3">
                          {past === null ? (
                            <span className="text-13 text-ink-muted">—</span>
                          ) : (
                            <span className="inline-flex flex-col">
                              <span>
                                <span className="font-mono font-medium">{formatAqi(past.value)}</span>
                                {c.unit && <span className="pl-1 text-12 text-ink-muted">{c.unit}</span>}
                              </span>
                              <span className="text-12 text-ink-muted">for {when(past.validAt)}</span>
                              {past.issuedAt !== newest && (
                                <span className="text-12 text-ink-muted">issued {when(past.issuedAt)}</span>
                              )}
                            </span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  )
}

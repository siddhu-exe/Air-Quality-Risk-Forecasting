import type { SourceLag } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatPercent } from '@/lib/format'

const hours = (h: number): string => (h < 1 ? `${Math.round(h * 60)} min` : `${h.toFixed(1)} h`)

function Tile({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-2.5 px-6 py-[22px]">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </Card>
  )
}

/** How far behind the data source is (the reason forecasts are or are not being issued), and how many stations get one. */
export function SourceLagCard({ lag, coverage }: { lag: SourceLag; coverage: number | null }) {
  return (
    <section aria-label="Data source" className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
      <Tile title={`Source lag${lag.source ? ` · ${lag.source}` : ''}`}>
        {lag.currentMedianHours === null ? (
          <p className="text-ink-2">No readings yet.</p>
        ) : (
          <>
            <p className="font-mono text-32">{hours(Math.max(lag.currentMedianHours, 0))}</p>
            <p className="text-13 text-ink-2">
              Median age of each station's newest reading; the oldest is {hours(Math.max(lag.currentMaxHours ?? 0, 0))}. Forecasts
              are only issued from data under 3 hours old.
            </p>
          </>
        )}
      </Tile>

      <Tile title="Stations with a forecast">
        <p className="font-mono text-32">{coverage === null ? '—' : formatPercent(coverage)}</p>
        <p className="text-13 text-ink-2">Share of station-hours with a forecast over the last 24 hours.</p>
      </Tile>

      <Tile title="Lag by day">
        {lag.daily.length === 0 ? (
          <p className="text-ink-2">No ingest runs recorded yet.</p>
        ) : (
          <table className="w-full border-collapse text-14">
            <caption className="sr-only">Median and worst station age at each ingest run, by day</caption>
            <thead>
              <tr className="text-left text-13 text-ink-muted">
                <th scope="col" className="py-1.5 font-medium">Day</th>
                <th scope="col" className="py-1.5 text-right font-medium">Median</th>
                <th scope="col" className="py-1.5 text-right font-medium">Worst</th>
              </tr>
            </thead>
            <tbody>
              {lag.daily.slice(-7).map((d) => (
                <tr key={d.day} className="border-t border-line-soft">
                  <th scope="row" className="py-1.5 text-left font-normal">{d.day}</th>
                  <td className="py-1.5 text-right font-mono">{hours(d.medianHours)}</td>
                  <td className="py-1.5 text-right font-mono">{hours(d.maxHours)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Tile>
    </section>
  )
}

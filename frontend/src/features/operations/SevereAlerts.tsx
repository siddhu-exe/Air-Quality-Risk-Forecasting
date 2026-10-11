import { Link } from 'react-router-dom'
import type { AlertStatus, GrapAlerts } from '@/api/schemas'
import { RangeBar } from '@/components/charts/RangeBar'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { categoryOf, formatAqi, SEVERE_THRESHOLD } from '@/lib/aqi'
import { formatPercent, formatWeekdayClock } from '@/lib/format'

const STATUS: Record<AlertStatus, { label: string; className: string }> = {
  active: { label: 'Active', className: 'bg-status-active-bg text-status-active-fg' },
  new: { label: 'New', className: 'bg-status-new-bg text-status-new-fg' },
  watch: { label: 'Watch', className: 'bg-status-watch-bg text-status-watch-fg' },
}

/** The bar spans the part of the scale where Severe decisions are made. */
const RANGE_DOMAIN = [200, 500] as const

export function SevereAlerts({ data }: { data: GrapAlerts }) {
  return (
    <Card as="section" aria-labelledby="alerts-title" className="flex flex-col gap-3 px-7 py-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="alerts-title" className="text-17 font-semibold">
          Severe alerts · next 24 hours
        </h2>
        <span className="text-13 text-ink-muted">
          Stations with a {formatPercent(data.alertMinProbability)}+ chance of AQI {SEVERE_THRESHOLD} or higher
        </span>
      </div>

      {data.alerts.length === 0 ? (
        <p className="py-6 text-ink-2">No station currently has that chance of reaching Severe in the next 24 hours.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse text-14">
            <thead>
              <tr className="text-left text-13 text-ink-muted">
                <th scope="col" className="py-2.5 pr-3 font-medium">Station</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Valid for</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Forecast</th>
                <th scope="col" className="px-3 py-2.5 font-medium">80% range</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Chance of Severe</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Copy-last says</th>
                <th scope="col" className="py-2.5 pl-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.alerts.map((alert) => {
                const status = STATUS[alert.status]
                return (
                  <tr key={alert.stationId} className="border-t border-line-soft">
                    <th scope="row" className="py-3.5 pr-3 text-left font-medium">
                      <Link to={`/stations/${alert.stationId}`} className="text-ink">
                        {alert.name}
                      </Link>
                    </th>
                    <td className="px-3 py-3.5 font-mono text-ink-2">{formatWeekdayClock(alert.validFor)}</td>
                    <td className="px-3 py-3.5 text-right font-mono font-medium">{formatAqi(alert.forecast24h)}</td>
                    <td className="px-3 py-3.5">
                      <RangeBar lo={alert.lo} hi={alert.hi} domain={RANGE_DOMAIN} mark={SEVERE_THRESHOLD} className="w-40" />
                      <span className="font-mono text-12 text-ink-muted">
                        {formatAqi(alert.lo)}–{formatAqi(alert.hi)}
                      </span>
                    </td>
                    <td className="px-3 py-3.5">
                      <span className="flex items-center gap-2">
                        <ProgressBar value={alert.pSevere} fillClassName="h-full bg-aqi-severe" className="w-[100px]" />
                        <span className="font-mono">{formatPercent(alert.pSevere)}</span>
                      </span>
                    </td>
                    <td className="px-3 py-3.5 text-ink-2">
                      {categoryOf(alert.persistence).label} ({formatAqi(alert.persistence)})
                    </td>
                    <td className="py-3.5 pl-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-13 ${status.className}`}>{status.label}</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-13 text-ink-muted">
        The range bar spans AQI {RANGE_DOMAIN[0]}–{RANGE_DOMAIN[1]}; the thin line marks {SEVERE_THRESHOLD}. Rows where
        copy-last disagrees are where the model adds most.
      </p>
    </Card>
  )
}

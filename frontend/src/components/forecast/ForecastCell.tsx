import type { Forecast } from '@/api/schemas'
import { TIER_FILL } from '@/components/aqi/tierClasses'
import { categoryOf, formatAqi } from '@/lib/aqi'
import { cn } from '@/lib/cn'
import { reasonLabel } from '@/lib/forecast'

interface ForecastCellProps {
  forecast: Forecast | undefined
  /** Shown after the number, e.g. µg/m³. */
  unit?: string
  className?: string
}

/**
 * One forecast in a table cell or list row: the value (with its AQI colour dot), or why there is none. An unavailable
 * forecast shows a short label on screen and the full reason as the tooltip and to screen readers; it is never blank
 * and never a substitute number. The experimental 24h AQI always shows plain persistence beside it.
 */
export function ForecastCell({ forecast, unit, className }: ForecastCellProps) {
  if (!forecast) {
    return <span className={cn('text-13 text-ink-muted', className)}>No forecast</span>
  }
  if (forecast.status !== 'ok' || forecast.value === null) {
    const reason = forecast.reason ?? 'no forecast'
    return (
      <span className={cn('inline-flex flex-col text-13 text-ink-muted', className)} title={reason}>
        <span>
          <span aria-hidden="true">— </span>
          {forecast.status === 'withheld' ? 'Not published' : reasonLabel(reason)}
        </span>
        <span className="sr-only">: {reason}</span>
      </span>
    )
  }

  const value = forecast.value
  return (
    <span className={cn('inline-flex flex-col', className)}>
      <span className="inline-flex items-center gap-2">
        {forecast.target === 'aqi' && (
          <span aria-hidden="true" className={`h-2 w-2 rounded-full ${TIER_FILL[categoryOf(value).key]}`} />
        )}
        <span className="font-mono font-medium">{formatAqi(value)}</span>
        {unit && <span className="text-12 text-ink-muted">{unit}</span>}
        {forecast.experimental && <span className="rounded bg-wash px-1.5 text-11 text-ink-2">experimental</span>}
      </span>
      {forecast.experimental && forecast.persistence !== null && (
        <span className="text-12 text-ink-muted">same as now: {formatAqi(forecast.persistence)}</span>
      )}
    </span>
  )
}

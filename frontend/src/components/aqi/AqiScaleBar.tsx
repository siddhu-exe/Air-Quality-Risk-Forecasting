import { AQI_SCALE_SEGMENTS, scalePercent } from '@/lib/aqi'
import { cn } from '@/lib/cn'
import { TIER_FILL } from './tierClasses'

const AXIS = [0, 100, 200, 300, 400, 500] as const

interface AqiScaleBarProps {
  /** Where "now" sits on the scale. */
  now?: number
  /** Forecast value (the solid marker). */
  forecast: number
  /** 80% interval, drawn as a translucent span under the bar. */
  range?: { lo: number; hi: number }
  /** Tick labels under the bar (desktop hero); omitted on the compact phone card. */
  showAxis?: boolean
  /** Bar thickness in px: 14 on desktop, 10 on the phone card. */
  thickness?: 10 | 14
  /** Describes the position for screen readers; the bar is otherwise decorative. */
  label: string
  className?: string
}

/** The coloured 0-500 CPCB scale with forecast, "now" and range markers. */
export function AqiScaleBar({
  now,
  forecast,
  range,
  showAxis = true,
  thickness = 14,
  label,
  className,
}: AqiScaleBarProps) {
  return (
    <div role="img" aria-label={label} className={cn('flex flex-col gap-2', className)}>
      <div
        className={cn('flex overflow-hidden rounded-full', thickness === 14 ? 'h-3.5' : 'h-2.5')}
        aria-hidden="true"
      >
        {AQI_SCALE_SEGMENTS.map((segment) => (
          <div key={segment.key} className={TIER_FILL[segment.key]} style={{ flex: segment.weight }} />
        ))}
      </div>

      {(range || now !== undefined) && (
        <div className="relative h-[22px]" aria-hidden="true">
          {range && (
            <div
              className="absolute top-0 h-1.5 rounded-[3px] bg-ink opacity-25"
              style={{
                left: `${scalePercent(range.lo)}%`,
                width: `${scalePercent(range.hi) - scalePercent(range.lo)}%`,
              }}
            />
          )}
          <div
            className="absolute -top-1 h-3.5 w-0.5 bg-ink"
            style={{ left: `${scalePercent(forecast)}%` }}
          />
          {now !== undefined && (
            <div
              className="absolute top-0 h-2 w-0.5 bg-ink-subtle"
              style={{ left: `${scalePercent(now)}%` }}
            />
          )}
        </div>
      )}

      {showAxis && (
        <div className="flex justify-between font-mono text-12 text-ink-muted" aria-hidden="true">
          {AXIS.map((tick) => (
            <span key={tick}>{tick}</span>
          ))}
        </div>
      )}
    </div>
  )
}

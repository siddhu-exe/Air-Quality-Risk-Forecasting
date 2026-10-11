import { useMemo } from 'react'
import { buildChartModel, CHART, describeSeries, type ChartInput } from '@/lib/chart'
import { cn } from '@/lib/cn'

interface ForecastChartProps extends ChartInput {
  /** Station name, used in the text description. */
  subject: string
  className?: string
}

function LegendItem({ swatch, children }: { swatch: React.ReactNode; children: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      {swatch}
      {children}
    </span>
  )
}

/**
 * Past 72 hours as a solid line, the forecast as a coloured line with its
 * likely range, and the "copy-last-value" baseline dashed. Hand-built SVG so
 * the scales, zones and tokens stay under our control.
 */
export function ForecastChart({ subject, target, history, forecast, className }: ForecastChartProps) {
  const model = useMemo(() => buildChartModel({ target, history, forecast }), [target, history, forecast])
  const first = history[0]
  const measure = target === 'aqi' ? 'AQI' : 'PM2.5'
  const label = describeSeries(subject, measure, model, first ? first.value : model.nowValue)
  const futureWidth = CHART.right - model.nowX
  const labelClass = 'fill-ink-muted font-mono text-11'

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          role="img"
          aria-label={label}
          className="block w-full min-w-[640px]"
        >
          <rect
            x={CHART.left}
            y={model.severeZone.y}
            width={CHART.right - CHART.left}
            height={model.severeZone.height}
            className="fill-aqi-severe"
            opacity={0.06}
          />
          <rect
            x={CHART.left}
            y={model.veryPoorZone.y}
            width={CHART.right - CHART.left}
            height={model.veryPoorZone.height}
            className="fill-aqi-very-poor"
            opacity={0.05}
          />
          {model.ticks.map((tick) => (
            <g key={tick.label}>
              <line x1={CHART.left} x2={CHART.right} y1={tick.y} y2={tick.y} className="stroke-line" strokeWidth={1} />
              <text x={46} y={tick.labelY} textAnchor="end" className={labelClass}>
                {tick.label}
              </text>
            </g>
          ))}
          <rect x={model.nowX} y={CHART.top} width={futureWidth} height={CHART.bottom - CHART.top} className="fill-accent" opacity={0.04} />
          <path d={model.bandPath} className="fill-accent" opacity={0.16} />
          <path d={model.pastPath} fill="none" className="stroke-ink" strokeWidth={2} strokeLinejoin="round" />
          <path d={model.persistencePath} fill="none" className="stroke-ink-subtle" strokeWidth={1.5} strokeDasharray="4 4" />
          <path d={model.medianPath} fill="none" className="stroke-accent" strokeWidth={2.5} strokeLinecap="round" />
          <line x1={model.nowX} x2={model.nowX} y1={CHART.top} y2={CHART.bottom} className="stroke-ink" strokeWidth={1} />
          <text x={model.nowX} y={322} textAnchor="middle" className="fill-ink font-sans text-12">
            now
          </text>
          <text x={CHART.left} y={322} className={labelClass}>
            −72h
          </text>
          <text x={model.midX} y={322} textAnchor="middle" className={labelClass}>
            −36h
          </text>
          <text x={CHART.right} y={322} textAnchor="end" className={labelClass}>
            {model.endLabel}
          </text>
        </svg>
      </div>

      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-13 text-ink-2" aria-label="Chart key">
        <li>
          <LegendItem swatch={<span aria-hidden="true" className="h-0.5 w-[18px] bg-ink" />}>Measured</LegendItem>
        </li>
        <li>
          <LegendItem swatch={<span aria-hidden="true" className="h-[3px] w-[18px] bg-accent" />}>Forecast</LegendItem>
        </li>
        <li>
          <LegendItem swatch={<span aria-hidden="true" className="h-2.5 w-[18px] bg-accent opacity-25" />}>
            {target === 'aqi' ? '80% range' : 'Likely range'}
          </LegendItem>
        </li>
        <li>
          <LegendItem
            swatch={<span aria-hidden="true" className="h-0 w-[18px] border-t-[1.5px] border-dashed border-ink-subtle" />}
          >
            Copy-last-value baseline
          </LegendItem>
        </li>
      </ul>
    </div>
  )
}

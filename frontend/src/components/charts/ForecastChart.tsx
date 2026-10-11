import { useId, useState } from 'react'
import type { ChartInput } from '@/lib/chart'
import { cn } from '@/lib/cn'
import { ForecastPlot } from './ForecastPlot'
import { SeriesTable } from './SeriesTable'

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

/** The station chart with its key, and a switch to the same numbers as a table. */
export function ForecastChart({ subject, target, history, forecast, className }: ForecastChartProps) {
  const [asTable, setAsTable] = useState(false)
  const tableId = useId()

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {asTable ? (
        <SeriesTable id={tableId} subject={subject} target={target} history={history} forecast={forecast} />
      ) : (
        <ForecastPlot subject={subject} target={target} history={history} forecast={forecast} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
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
        <button
          type="button"
          aria-controls={asTable ? tableId : undefined}
          onClick={() => setAsTable((v) => !v)}
          className="link min-h-target text-14"
        >
          {asTable ? 'View as chart' : 'View as table'}
        </button>
      </div>
    </div>
  )
}

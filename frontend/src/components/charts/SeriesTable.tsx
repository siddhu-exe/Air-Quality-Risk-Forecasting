import { useLayoutEffect, useMemo, useRef } from 'react'
import { buildSeriesRows, type ChartInput } from '@/lib/chart'
import { formatWhen } from '@/lib/format'

const round = (n: number): number => Math.round(n)

/** The chart's numbers, hour by hour: the accessible twin of the plot. Opens scrolled to "now". */
export function SeriesTable({ id, subject, target, history, forecast }: ChartInput & { id: string; subject: string }) {
  const rows = useMemo(() => buildSeriesRows({ history, forecast }), [history, forecast])
  const nowIso = history[history.length - 1]?.t ?? ''
  const unit = target === 'aqi' ? 'AQI' : 'PM2.5, µg/m³'
  const scrollerRef = useRef<HTMLDivElement>(null)
  const nowRowRef = useRef<HTMLTableRowElement>(null)

  useLayoutEffect(() => {
    const scroller = scrollerRef.current
    const row = nowRowRef.current
    if (scroller && row) scroller.scrollTop = Math.max(0, row.offsetTop - scroller.clientHeight / 2)
  }, [rows])

  return (
    <div
      id={id}
      ref={scrollerRef}
      // A scrollable region must be focusable so keyboard users can scroll it.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      role="region"
      aria-label={`${subject}: hourly values (${unit})`}
      className="max-h-80 overflow-auto rounded-lg border border-line-soft"
    >
      <table className="w-full min-w-[420px] border-collapse text-14">
        <caption className="sr-only">
          Hourly {unit} for {subject}: measured over the past 72 hours, then the published forecast points.
        </caption>
        <thead className="sticky top-0 bg-surface text-left text-13 text-ink-muted shadow-[0_1px_0_0_theme(colors.line.soft)]">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Time
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Measured
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Forecast
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isNow = row.t === nowIso
            return (
              <tr
                key={row.t}
                ref={isNow ? nowRowRef : undefined}
                className={isNow ? 'border-t border-line-soft bg-wash font-medium' : 'border-t border-line-soft'}
              >
                <th scope="row" className="px-3 py-2 text-left font-normal">
                  {isNow ? 'Now' : formatWhen(row.t, nowIso)}
                </th>
                <td className="px-3 py-2 text-right font-mono">{row.measured === undefined ? '—' : round(row.measured)}</td>
                <td className="px-3 py-2 text-right font-mono">{row.forecast === undefined ? '—' : round(row.forecast)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

import { useLayoutEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { buildChartModel, CHART, describeSeries, nearestSample, type ChartInput, type ChartSample } from '@/lib/chart'
import { cn } from '@/lib/cn'
import { formatWhen } from '@/lib/format'

interface ForecastPlotProps extends ChartInput {
  /** Station name, used in the text description. */
  subject: string
}

const UNIT: Record<ChartInput['target'], string> = { aqi: '', pm25: ' µg/m³' }

const round = (n: number): number => Math.round(n)

function Readout({ sample, nowIso, unit }: { sample: ChartSample; nowIso: string; unit: string }) {
  const isNow = sample.t === nowIso
  return (
    <>
      <p className="text-12 text-ink-muted">{isNow ? 'Now' : formatWhen(sample.t, nowIso)}</p>
      <p className="font-mono text-15 font-medium">
        {round(sample.value)}
        <span className="text-12 font-normal text-ink-muted">{unit}</span>
        <span className="ml-2 font-sans text-12 font-normal text-ink-muted">
          {sample.kind === 'measured' ? 'measured' : 'forecast'}
        </span>
      </p>
    </>
  )
}

/**
 * The SVG chart plus a hover/tap readout. Past 72 hours as a solid line, the
 * forecast as a coloured line through the published forecast points, and the
 * "copy-last-value" baseline dashed. The readout is for pointer users; the same numbers are in
 * the table view, which is what keyboard and screen-reader users get.
 */
export function ForecastPlot({ subject, target, history, forecast }: ForecastPlotProps) {
  const model = useMemo(() => buildChartModel({ target, history, forecast }), [target, history, forecast])
  const nowIso = history[history.length - 1]?.t ?? ''
  const first = history[0]
  const measure = target === 'aqi' ? 'AQI' : 'PM2.5'
  const label = describeSeries(subject, measure, model, first ? first.value : model.nowValue)
  const futureWidth = CHART.right - model.nowX
  const labelClass = 'fill-ink-muted font-mono text-11'

  const [activeIso, setActiveIso] = useState<string>()
  const active = activeIso ? model.samples.find((s) => s.t === activeIso) : undefined
  const surfaceRef = useRef<HTMLDivElement>(null)
  const scrollerRef = useRef<HTMLDivElement>(null)

  // On a phone the chart is wider than the screen: start at "now", where the forecast is.
  useLayoutEffect(() => {
    const scroller = scrollerRef.current
    if (scroller) scroller.scrollLeft = scroller.scrollWidth
  }, [model])

  function track(event: PointerEvent<HTMLDivElement>) {
    const surface = surfaceRef.current
    if (!surface) return
    const rect = surface.getBoundingClientRect()
    if (rect.width === 0) return
    const x = ((event.clientX - rect.left) / rect.width) * CHART.width
    setActiveIso(nearestSample(model.samples, x)?.t)
  }

  const leftPct = active ? (active.x / CHART.width) * 100 : 0
  // Keep the readout inside the chart: flip it to the other side of the line near either edge.
  const anchor = leftPct > 65 ? 'translate-x-[calc(-100%-12px)]' : 'translate-x-3'

  return (
    <>
      <div
        ref={scrollerRef}
        // A scrollable region must be focusable so keyboard users can scroll it.
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        role="group"
        aria-label={`${label}. Scrolls sideways on small screens.`}
        className="overflow-x-auto rounded-lg"
      >
        <div
          ref={surfaceRef}
          className="relative min-w-[640px] cursor-crosshair"
          onPointerDown={track}
          onPointerMove={track}
          onPointerLeave={(event) => {
            // A finger lifting is not "leaving": keep the readout so it can be read.
            if (event.pointerType === 'mouse') setActiveIso(undefined)
          }}
        >
          <svg viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-label={label} className="block w-full">
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
            <path d={model.pastPath} fill="none" className="stroke-ink" strokeWidth={2} strokeLinejoin="round" />
            <path d={model.persistencePath} fill="none" className="stroke-ink-subtle" strokeWidth={1.5} strokeDasharray="4 4" />
            {model.forecastPath && (
              <path d={model.forecastPath} fill="none" className="stroke-accent" strokeWidth={2.5} strokeLinecap="round" />
            )}
            {model.samples
              .filter((sample) => sample.kind === 'forecast')
              .map((sample) => (
                <circle key={sample.t} cx={sample.x} cy={sample.y} r={4.5} className="fill-accent" />
              ))}
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
            {active && (
              <g className="pointer-events-none">
                <line x1={active.x} x2={active.x} y1={CHART.top} y2={CHART.bottom} className="stroke-ink-subtle" strokeWidth={1} />
                <circle
                  cx={active.x}
                  cy={active.y}
                  r={5}
                  strokeWidth={2.5}
                  className={active.kind === 'measured' ? 'fill-surface stroke-ink' : 'fill-surface stroke-accent'}
                />
              </g>
            )}
          </svg>
          {active && (
            <div
              aria-hidden="true"
              data-testid="chart-readout"
              className={cn(
                'pointer-events-none absolute top-2 min-w-32 rounded-lg border border-line bg-surface px-3 py-2 shadow-sm',
                anchor,
              )}
              style={{ left: `${leftPct}%` }}
            >
              <Readout sample={active} nowIso={nowIso} unit={UNIT[target]} />
            </div>
          )}
        </div>
      </div>
      <p className="-mt-2 text-12 text-ink-muted md:hidden">Swipe sideways for earlier hours. Tap the chart to read a value.</p>
    </>
  )
}

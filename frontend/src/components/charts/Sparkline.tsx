import { useMemo } from 'react'

interface SparklineProps {
  values: readonly number[]
  /** Text alternative: what the line shows and where it ends. */
  label: string
  /** Default range; widened if the data leaves it. */
  domain?: readonly [number, number]
}

const W = 300
const H = 70
const PAD = 6

/** Thirty-day skill line with a dashed zero line: below it the model is losing. */
export function Sparkline({ values, label, domain = [-0.15, 0.25] }: SparklineProps) {
  const geometry = useMemo(() => {
    const lo = Math.min(domain[0], ...values)
    const hi = Math.max(domain[1], ...values)
    const y = (v: number): number => H - PAD - ((v - lo) / (hi - lo)) * (H - 2 * PAD)
    const points = values.map((v, i) => `${((i * W) / (values.length - 1)).toFixed(1)},${y(v).toFixed(1)}`)
    return {
      line: `M${points.join(' L')}`,
      area: `M0,${y(lo).toFixed(1)} L${points.join(' L')} L${W},${y(lo).toFixed(1)} Z`,
      zeroY: y(0).toFixed(1),
    }
  }, [values, domain])

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} role="img" aria-label={label}>
      <line x1={0} x2={W} y1={geometry.zeroY} y2={geometry.zeroY} className="stroke-brand" strokeWidth={1} strokeDasharray="3 3" opacity={0.7} vectorEffect="non-scaling-stroke" />
      <path d={geometry.area} className="fill-accent" opacity={0.08} />
      <path d={geometry.line} fill="none" className="stroke-accent" strokeWidth={1.8} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

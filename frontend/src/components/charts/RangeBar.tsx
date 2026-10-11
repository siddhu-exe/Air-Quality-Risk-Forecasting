import { cn } from '@/lib/cn'

interface RangeBarProps {
  lo: number
  hi: number
  /** Value range the bar spans. */
  domain: readonly [number, number]
  /** A reference line (the 401 Severe line). */
  mark?: number
  className?: string
}

/** Decorative interval bar; the numbers beside it carry the meaning. */
export function RangeBar({ lo, hi, domain, mark, className }: RangeBarProps) {
  const [min, max] = domain
  const pct = (v: number): number => ((Math.min(Math.max(v, min), max) - min) / (max - min)) * 100
  return (
    <span aria-hidden="true" className={cn('relative block h-2 rounded-full bg-line-soft', className)}>
      <span
        className="absolute inset-y-0 rounded-full bg-accent opacity-35"
        style={{ left: `${pct(lo)}%`, width: `${pct(hi) - pct(lo)}%` }}
      />
      {mark !== undefined && (
        <span className="absolute -top-[3px] h-3.5 w-px bg-aqi-severe" style={{ left: `${pct(mark)}%` }} />
      )}
    </span>
  )
}

import { cn } from '@/lib/cn'

interface ProgressBarProps {
  /** 0-1; values outside are clamped. */
  value: number
  /** Tailwind background class for the fill, e.g. `bg-aqi-severe`. */
  fillClassName: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const HEIGHT = { sm: 'h-1.5', md: 'h-2', lg: 'h-2.5' } as const

/**
 * A decorative proportion bar. It always sits next to the number it draws, so
 * it is hidden from assistive tech rather than announced twice.
 */
export function ProgressBar({ value, fillClassName, size = 'sm', className }: ProgressBarProps) {
  const pct = Math.min(Math.max(value, 0), 1) * 100
  return (
    <span
      aria-hidden="true"
      className={cn('flex overflow-hidden rounded-full bg-line-soft', HEIGHT[size], className)}
    >
      <span className={fillClassName} style={{ width: `${pct}%` }} />
    </span>
  )
}

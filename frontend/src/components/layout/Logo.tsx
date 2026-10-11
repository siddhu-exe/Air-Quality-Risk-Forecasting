import { Link } from 'react-router-dom'
import { cn } from '@/lib/cn'

/** Ring with a red haze line. Decorative: the wordmark beside it names the product. */
function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 22 22" aria-hidden="true" className={cn('h-5 w-5 md:h-[22px] md:w-[22px]', className)}>
      <circle cx="11" cy="11" r="10" fill="none" className="stroke-ink" strokeWidth="1.5" />
      <path
        d="M4 13c3-3 5 0 7-2s4-3 7 0"
        fill="none"
        className="stroke-brand"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Logo() {
  return (
    <Link to="/" className="flex min-h-target items-center gap-2 text-ink no-underline hover:text-ink md:gap-2.5">
      <LogoMark />
      <span className="font-semibold tracking-[-0.01em]">Delhi Air</span>
      <span className="hidden text-ink-muted md:inline">Forecast</span>
    </Link>
  )
}

import { cn } from '@/lib/cn'

/** 24 hourly cells, oldest first: blue = reading received, orange = gap. */
export function FreshnessStrip({ hourly }: { hourly: readonly boolean[] }) {
  const received = hourly.filter(Boolean).length
  return (
    <span role="img" aria-label={`${received} of ${hourly.length} hourly readings received`} className="flex gap-0.5">
      {hourly.map((ok, hour) => (
        <span key={hour} className={cn('h-[18px] w-2 rounded-sm', ok ? 'bg-fresh-ok' : 'bg-fresh-gap')} />
      ))}
    </span>
  )
}

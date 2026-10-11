import { categoryOf } from '@/lib/aqi'
import { cn } from '@/lib/cn'
import { TIER_PILL } from './tierClasses'

interface CategoryPillProps {
  /** AQI value; the pill shows its CPCB category. */
  aqi: number
  /** `md` is the hero badge, `sm` the inline one used in tables and cards. */
  size?: 'sm' | 'md'
  className?: string
}

/** CPCB category badge ("Very Poor"). Text carries the meaning, colour reinforces it. */
export function CategoryPill({ aqi, size = 'sm', className }: CategoryPillProps) {
  const category = categoryOf(aqi)
  return (
    <span
      className={cn(
        'inline-block whitespace-nowrap rounded-full',
        size === 'md' ? 'px-3 py-1 font-medium' : 'px-2.5 py-0.5 text-13',
        TIER_PILL[category.key],
        className,
      )}
    >
      {category.label}
    </span>
  )
}

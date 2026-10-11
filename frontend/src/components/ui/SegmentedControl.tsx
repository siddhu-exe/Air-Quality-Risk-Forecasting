import { cn } from '@/lib/cn'

interface Option<V extends string> {
  value: V
  label: string
}

interface SegmentedControlProps<V extends string> {
  /** Accessible name for the group, e.g. "Choose measure". */
  label: string
  options: readonly Option<V>[]
  value: V
  onChange: (value: V) => void
  className?: string
}

/** Pill-shaped toggle group (AQI | PM2.5, alert rule). Each option is a toggle button. */
export function SegmentedControl<V extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: SegmentedControlProps<V>) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('inline-flex rounded-full bg-wash p-1', className)}
    >
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              'min-h-10 rounded-full px-4 text-14 text-ink transition-colors duration-150',
              selected ? 'bg-surface font-medium' : 'hover:bg-line-strong/40',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

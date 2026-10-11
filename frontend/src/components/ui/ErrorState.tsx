import { Card } from './Card'
import { cn } from '@/lib/cn'

interface ErrorStateProps {
  title?: string
  message: string
  /** Shown as a button when provided. */
  onRetry?: () => void
  className?: string
}

/** What a failed load looks like: a cause in plain words and a way to try again. */
export function ErrorState({
  title = 'Could not load this section',
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <Card role="alert" className={cn('flex flex-col items-start gap-3 p-6', className)}>
      <h2 className="text-17 font-semibold">{title}</h2>
      <p className="text-ink-2">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="min-h-target rounded-full bg-ink px-5 font-medium text-white hover:bg-ink-2"
        >
          Try again
        </button>
      )}
    </Card>
  )
}

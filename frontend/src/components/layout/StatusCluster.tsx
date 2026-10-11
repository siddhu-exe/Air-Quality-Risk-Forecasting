import { useHealth } from '@/api/queries'
import { usingMockData } from '@/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/lib/cn'
import { formatUpdated } from '@/lib/format'

/** "Sample readings" badge (mock mode only) and the last-updated stamp. */
export function StatusCluster({ className }: { className?: string }) {
  const { data, isPending } = useHealth()

  return (
    <div className={cn('flex flex-wrap items-center gap-3', className)}>
      {usingMockData && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-caution-bg px-2.5 py-1 text-13 text-caution-fg">
          Sample readings · live feed pending
        </span>
      )}
      {isPending ? (
        // Reserve the stamp's width so the header does not shift when it arrives.
        <Skeleton className="h-4 w-44" />
      ) : data ? (
        <span className="font-mono text-13 text-ink-muted">{formatUpdated(data.dataAsOf)}</span>
      ) : null}
    </div>
  )
}

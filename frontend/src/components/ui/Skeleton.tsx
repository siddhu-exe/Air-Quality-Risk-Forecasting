import { cn } from '@/lib/cn'

/** Placeholder block shown while data loads; size it with className to reserve the final space. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('animate-pulse rounded-lg bg-wash', className)} />
}

import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/cn'

/** Small uppercase label above a heading or card ("TOMORROW · MON 12 OCT"). */
export function Eyebrow({ className, ...props }: ComponentPropsWithoutRef<'p'>) {
  return <p className={cn('text-13 uppercase tracking-caps text-ink-muted', className)} {...props} />
}

import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

/** Page body: 1360 px column, 40 px gutters on desktop, 20 px on phones. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('mx-auto flex w-full max-w-page flex-col gap-4 px-5 pb-18 pt-5 md:gap-6 md:px-10 md:pt-8', className)}>
      {children}
    </div>
  )
}

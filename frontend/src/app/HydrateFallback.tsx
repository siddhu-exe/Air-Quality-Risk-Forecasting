import { Page } from '@/components/ui/Page'
import { Skeleton } from '@/components/ui/Skeleton'

/** Shown while the first route chunk loads. */
export function HydrateFallback() {
  return (
    <Page className="pt-10">
      <Skeleton className="h-72 w-full" />
    </Page>
  )
}

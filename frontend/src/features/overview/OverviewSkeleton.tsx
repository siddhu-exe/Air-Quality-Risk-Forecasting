import { Card } from '@/components/ui/Card'
import { Page } from '@/components/ui/Page'
import { Skeleton } from '@/components/ui/Skeleton'

/** Holds the hero's and the stations' footprint so nothing jumps when data arrives. */
export function OverviewSkeleton() {
  return (
    <Page className="md:gap-7 md:pt-10">
      <span className="sr-only" role="status">
        Loading the forecast
      </span>
      <div className="flex flex-wrap gap-4 md:gap-6">
        <Card className="flex min-w-0 flex-[999_1_560px] flex-col gap-5 p-[22px] md:px-9 md:py-8">
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-24 w-48 md:h-32 md:w-72" />
          <Skeleton className="h-3.5 w-full rounded-full" />
          <Skeleton className="h-12 w-full" />
        </Card>
        <Skeleton className="min-h-52 flex-[1_1_340px] rounded-2xl" />
      </div>
      <Skeleton className="h-[540px] rounded-2xl" />
    </Page>
  )
}

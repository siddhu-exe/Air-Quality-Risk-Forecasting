import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'

/** Chart, horizon cards and detail row, sized like the loaded page. */
export function StationDetailSkeleton() {
  return (
    <>
      <span className="sr-only" role="status">
        Loading the station forecast
      </span>
      <Card className="flex flex-col gap-4 px-7 py-6">
        <Skeleton className="h-6 w-72" />
        <Skeleton className="h-[340px] w-full" />
      </Card>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-[190px] rounded-2xl" />
        ))}
      </div>
      <div className="flex flex-wrap gap-6">
        <Skeleton className="h-72 min-w-0 flex-[999_1_560px] rounded-2xl" />
        <Skeleton className="h-72 min-w-0 flex-[1_1_300px] rounded-2xl" />
      </div>
    </>
  )
}

/** Whole-page placeholder while the station list itself is loading. */
export function StationsPageSkeleton() {
  return (
    <>
      <div className="flex flex-wrap gap-2">
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <Skeleton key={i} className="h-11 w-28 rounded-full" />
        ))}
      </div>
      <Skeleton className="h-16 w-72" />
      <StationDetailSkeleton />
    </>
  )
}

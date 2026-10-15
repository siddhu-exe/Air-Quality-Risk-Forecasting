import { formatClock, formatDay } from '@/lib/format'

/**
 * Shown when the API says the newest reading is over three hours old (or there is none). It uses the same caution
 * tokens as the "sample readings" badge.
 */
export function StaleBanner({ dataAsOf }: { dataAsOf: string | null }) {
  return (
    <div role="status" className="rounded-xl bg-caution-bg px-4 py-3 text-14 text-caution-fg">
      {dataAsOf === null
        ? 'There are no readings yet, so nothing can be forecast.'
        : `Readings are delayed. The newest data is from ${formatClock(dataAsOf)} IST on ${formatDay(dataAsOf)}, so treat what you see with extra care; forecasts are only issued from fresh data.`}
    </div>
  )
}

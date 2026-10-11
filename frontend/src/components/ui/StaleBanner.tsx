import { formatClock, formatDay } from '@/lib/format'

/**
 * Shown when the API says the newest reading is over three hours old. It uses
 * the same caution tokens as the "sample readings" badge.
 */
export function StaleBanner({ dataAsOf }: { dataAsOf: string }) {
  return (
    <div
      role="status"
      className="rounded-xl bg-caution-bg px-4 py-3 text-14 text-caution-fg"
    >
      Readings are delayed. The newest data is from {formatClock(dataAsOf)} IST on {formatDay(dataAsOf)}, so
      treat these forecasts with extra care.
    </div>
  )
}

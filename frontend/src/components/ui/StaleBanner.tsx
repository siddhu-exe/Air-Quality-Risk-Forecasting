import { formatClock, formatDay } from '@/lib/format'

/**
 * Shown when the API says the newest reading is over three hours old (or there is none). It uses the same caution
 * tokens as the "sample readings" badge. It always names the time of the latest data first.
 */
export function StaleBanner({ dataAsOf }: { dataAsOf: string | null }) {
  return (
    <div role="status" className="rounded-xl bg-caution-bg px-4 py-3 text-14 text-caution-fg">
      {dataAsOf === null ? (
        'There are no readings yet, so nothing can be forecast.'
      ) : (
        <>
          <strong className="font-semibold">
            Latest data: {formatClock(dataAsOf)} IST on {formatDay(dataAsOf)}.
          </strong>{' '}
          Readings are delayed, so no current forecast is issued; forecasts are only issued from fresh data. Any forecast
          shown as &ldquo;last issued&rdquo; is from the past.
        </>
      )}
    </div>
  )
}

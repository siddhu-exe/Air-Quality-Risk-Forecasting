import { useMemo, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { describeError } from '@/api/describeError'
import { useBacktest, useStationForecast, useStations } from '@/api/queries'
import type { ForecastTarget } from '@/api/schemas'
import { ForecastChart } from '@/components/charts/ForecastChart'
import { Card } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { Page } from '@/components/ui/Page'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { StaleBanner } from '@/components/ui/StaleBanner'
import { chartForecast, rankSummariesByNow } from '@/lib/forecast'
import { cn } from '@/lib/cn'
import { ProductCards } from './ProductCards'
import { PollutantsTable } from './PollutantsTable'
import { StationHeader } from './StationHeader'
import { StationPills } from './StationPills'
import { StationDetailSkeleton, StationsPageSkeleton } from './StationsSkeleton'
import { WeatherCard } from './WeatherCard'

const MEASURES = [
  { value: 'aqi', label: 'AQI' },
  { value: 'pm25', label: 'PM2.5' },
] as const

const CHART_TITLE: Record<ForecastTarget, string> = {
  aqi: 'Past 72 hours and the published forecasts (AQI)',
  pm25: 'Past 72 hours and the published forecasts (PM2.5, µg/m³)',
}

/** One station: now, the 72 h story, three horizons, pollutants and weather. */
export function StationsPage() {
  const { stationId } = useParams()
  const [target, setTarget] = useState<ForecastTarget>('aqi')
  const stationsQuery = useStations()
  const forecastQuery = useStationForecast(stationId, target)
  const backtest = useBacktest()

  // Worst first, matching the Overview table; stations with no current reading last.
  const stations = useMemo(() => rankSummariesByNow(stationsQuery.data?.stations ?? []), [stationsQuery.data])

  if (stationsQuery.isPending) {
    return (
      <Page>
        <StationsPageSkeleton />
      </Page>
    )
  }
  if (stationsQuery.error) {
    return (
      <Page>
        <ErrorState message={describeError(stationsQuery.error)} onRetry={() => void stationsQuery.refetch()} />
      </Page>
    )
  }

  const first = stations[0]
  if (!stationId && first) return <Navigate to={`/stations/${first.id}`} replace />

  const station = stations.find((s) => s.id === stationId)
  if (!station) {
    return (
      <Page>
        <Card className="flex flex-col items-start gap-3 p-6">
          <h1 className="text-17 font-semibold">Station not found</h1>
          <p className="text-ink-2">There is no station called “{stationId}” in the forecast.</p>
          {first && (
            <Link to={`/stations/${first.id}`} className="link">
              Go to {first.name}
            </Link>
          )}
        </Card>
      </Page>
    )
  }

  const forecast = forecastQuery.data
  // Showing the previous station's series while the new one loads: dim it so it is not mistaken for current.
  const switching = forecastQuery.isPlaceholderData

  return (
    <Page>
      {stationsQuery.data.stale && <StaleBanner dataAsOf={stationsQuery.data.dataAsOf} />}
      <StationPills stations={stations} selectedId={station.id} />
      <StationHeader station={station} />

      {forecastQuery.isPending ? (
        <StationDetailSkeleton />
      ) : forecastQuery.error && !forecast ? (
        <ErrorState message={describeError(forecastQuery.error)} onRetry={() => void forecastQuery.refetch()} />
      ) : forecast ? (
        <div className={cn('flex flex-col gap-4 transition-opacity md:gap-6', switching && 'opacity-60')} aria-busy={switching}>
          <Card as="section" aria-labelledby="chart-title" className="flex flex-col gap-4 px-5 py-6 md:px-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="chart-title" className="text-17 font-semibold">
                {CHART_TITLE[forecast.target]}
              </h2>
              <SegmentedControl label="Choose measure" options={MEASURES} value={target} onChange={setTarget} />
            </div>
            {forecast.history.length < 2 ? (
              <p className="rounded-lg bg-wash px-4 py-10 text-center text-ink-2">
                There are no recent {forecast.target === 'aqi' ? 'AQI' : 'PM2.5'} readings for this station, so there is
                nothing to draw. The cards below say why each forecast is missing.
              </p>
            ) : (
              <ForecastChart
                subject={forecast.station.name}
                target={forecast.target}
                history={forecast.history}
                forecast={chartForecast(forecast.forecasts)}
              />
            )}
          </Card>

          <ProductCards forecasts={forecast.forecasts} evidence={backtest.data?.evidence} asOf={forecast.dataAsOf ?? forecast.generatedAt} />

          <div className="flex flex-wrap gap-4 md:gap-6">
            <PollutantsTable pollutants={forecast.pollutants} />
            <WeatherCard weather={forecast.weather} />
          </div>
        </div>
      ) : null}
    </Page>
  )
}

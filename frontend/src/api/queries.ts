import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './index'
import type { ForecastTarget } from './schemas'

const FIVE_MINUTES = 5 * 60 * 1000

export const queryKeys = {
  health: ['health'] as const,
  overview: ['overview'] as const,
  stations: ['stations'] as const,
  stationForecast: (id: string, target: ForecastTarget) => ['stations', id, 'forecast', target] as const,
  grapAlerts: ['alerts', 'grap'] as const,
  modelHealth: ['model-health'] as const,
  backtest: ['backtest'] as const,
}

/** Live data refreshes every five minutes while the tab is visible. */
const live = { refetchInterval: FIVE_MINUTES, refetchIntervalInBackground: false } as const

export const useHealth = () =>
  useQuery({ queryKey: queryKeys.health, queryFn: ({ signal }) => api.health(signal), ...live })

export const useOverview = () =>
  useQuery({ queryKey: queryKeys.overview, queryFn: ({ signal }) => api.overview(signal), ...live })

export const useStations = () =>
  useQuery({ queryKey: queryKeys.stations, queryFn: ({ signal }) => api.stations(signal), ...live })

/** Keeps the previous series on screen while a new station or measure loads. */
export const useStationForecast = (id: string | undefined, target: ForecastTarget) =>
  useQuery({
    queryKey: queryKeys.stationForecast(id ?? '', target),
    queryFn: ({ signal }) => api.stationForecast(id as string, target, signal),
    enabled: id !== undefined && id !== '',
    placeholderData: keepPreviousData,
    ...live,
  })

export const useGrapAlerts = () =>
  useQuery({ queryKey: queryKeys.grapAlerts, queryFn: ({ signal }) => api.grapAlerts(signal), ...live })

export const useModelHealth = () =>
  useQuery({ queryKey: queryKeys.modelHealth, queryFn: ({ signal }) => api.modelHealth(signal), ...live })

/** Static backtest numbers: no polling, kept fresh for the whole session. */
export const useBacktest = () =>
  useQuery({
    queryKey: queryKeys.backtest,
    queryFn: ({ signal }) => api.backtest(signal),
    staleTime: Infinity,
  })

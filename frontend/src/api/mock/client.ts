import { ApiError } from '../http'
import {
  BacktestSchema,
  GrapAlertsSchema,
  HealthSchema,
  ModelHealthSchema,
  OverviewSchema,
  StationForecastSchema,
  StationsSchema,
} from '../schemas'
import type { ApiClient } from '../types'
import type * as MockData from './data'

/**
 * Serves the sample fixtures through the same schemas as the real client, so a
 * fixture that drifts from the contract fails here, not in production. The
 * fixtures are imported on demand so they are a separate chunk that real-API
 * deployments never download.
 */
export function createMockClient({ latencyMs = 0 }: { latencyMs?: number } = {}): ApiClient {
  const respond = async <T>(produce: (data: typeof MockData) => T): Promise<T> => {
    const data = await import('./data')
    if (latencyMs > 0) await new Promise((resolve) => setTimeout(resolve, latencyMs))
    return produce(data)
  }

  return {
    health: () => respond((d) => HealthSchema.parse(d.healthFixture)),
    overview: () => respond((d) => OverviewSchema.parse(d.overviewFixture)),
    stations: () => respond((d) => StationsSchema.parse(d.stationsFixture)),
    stationForecast: (id, target) =>
      respond((d) => {
        const fixture = d.stationForecastFixture(id, target)
        if (!fixture) throw new ApiError(`Unknown station "${id}".`, { status: 404 })
        return StationForecastSchema.parse(fixture)
      }),
    grapAlerts: () => respond((d) => GrapAlertsSchema.parse(d.grapAlertsFixture)),
    modelHealth: () => respond((d) => ModelHealthSchema.parse(d.modelHealthFixture)),
    backtest: () => respond((d) => BacktestSchema.parse(d.backtestFixture)),
  }
}

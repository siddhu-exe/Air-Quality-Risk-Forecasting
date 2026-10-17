import {
  BacktestSchema,
  GrapAlertsSchema,
  HealthSchema,
  ModelHealthSchema,
  OverviewSchema,
  StationForecastSchema,
  StationsSchema,
} from './schemas'
import backtest from './contract/backtest.json'
import grapAlerts from './contract/grap_alerts.json'
import health from './contract/health.json'
import modelHealth from './contract/model_health.json'
import overview from './contract/overview.json'
import stationForecastAqi from './contract/station_forecast_aqi.json'
import stationForecastPm25 from './contract/station_forecast_pm25.json'
import stations from './contract/stations.json'

// These files are the API's real responses, pinned by tests/test_api_contract.py. If the backend renames a key,
// that suite fails; if a schema here disagrees with a key, this one does (the 2026-10 forecast6H/forecast6h bug).
describe('API contract: the zod schemas parse what the API actually sends', () => {
  const cases: [string, { safeParse: (v: unknown) => { success: boolean; error?: unknown } }, unknown][] = [
    ['health', HealthSchema, health],
    ['overview', OverviewSchema, overview],
    ['stations', StationsSchema, stations],
    ['station forecast (aqi)', StationForecastSchema, stationForecastAqi],
    ['station forecast (pm25)', StationForecastSchema, stationForecastPm25],
    ['grap alerts', GrapAlertsSchema, grapAlerts],
    ['model health', ModelHealthSchema, modelHealth],
    ['backtest', BacktestSchema, backtest],
  ]
  it.each(cases)('%s', (_name, schema, body) => {
    const result = schema.safeParse(body)
    expect(result.success, JSON.stringify(result.error ?? null, null, 1)).toBe(true)
  })
})

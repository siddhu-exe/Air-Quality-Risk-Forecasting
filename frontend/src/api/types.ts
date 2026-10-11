import type {
  Backtest,
  ForecastTarget,
  GrapAlerts,
  Health,
  ModelHealth,
  Overview,
  StationForecast,
  Stations,
} from './schemas'

/** What the UI needs from the backend; implemented by the HTTP and mock clients. */
export interface ApiClient {
  health(signal?: AbortSignal): Promise<Health>
  overview(signal?: AbortSignal): Promise<Overview>
  stations(signal?: AbortSignal): Promise<Stations>
  stationForecast(id: string, target: ForecastTarget, signal?: AbortSignal): Promise<StationForecast>
  grapAlerts(signal?: AbortSignal): Promise<GrapAlerts>
  modelHealth(signal?: AbortSignal): Promise<ModelHealth>
  backtest(signal?: AbortSignal): Promise<Backtest>
}

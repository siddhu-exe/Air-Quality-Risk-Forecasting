import type { z } from 'zod'
import { env } from '@/config/env'
import {
  BacktestSchema,
  GrapAlertsSchema,
  HealthSchema,
  ModelHealthSchema,
  OverviewSchema,
  StationForecastSchema,
  StationsSchema,
  type ForecastTarget,
} from './schemas'
import type { ApiClient } from './types'

export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, options?: { status?: number; cause?: unknown }) {
    super(message, options?.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'ApiError'
    this.status = options?.status
  }
}

/** GETs `path` under the API base URL and returns the body parsed by `schema`. */
export async function getJson<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  { signal, baseUrl = env.apiBaseUrl }: { signal?: AbortSignal; baseUrl?: string } = {},
): Promise<z.infer<S>> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      headers: { Accept: 'application/json' },
      ...(signal ? { signal } : {}),
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiError('Could not reach the forecast service.', { cause })
  }

  if (!response.ok) {
    throw new ApiError(`The forecast service answered ${response.status}.`, { status: response.status })
  }

  let body: unknown
  try {
    body = await response.json()
  } catch (cause) {
    throw new ApiError('The forecast service sent an unreadable response.', { cause })
  }

  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    // The contract is ours, so a mismatch is a bug worth a loud console message.
    console.error(`Unexpected response shape from ${path}`, parsed.error.issues)
    throw new ApiError('The forecast service sent data in an unexpected shape.', { cause: parsed.error })
  }
  return parsed.data
}

export function createHttpClient(baseUrl: string = env.apiBaseUrl): ApiClient {
  const opts = (signal?: AbortSignal) => ({ baseUrl, ...(signal ? { signal } : {}) })
  return {
    health: (signal) => getJson('/health', HealthSchema, opts(signal)),
    overview: (signal) => getJson('/overview', OverviewSchema, opts(signal)),
    stations: (signal) => getJson('/stations', StationsSchema, opts(signal)),
    stationForecast: (id: string, target: ForecastTarget, signal) =>
      getJson(
        `/stations/${encodeURIComponent(id)}/forecast?target=${target}`,
        StationForecastSchema,
        opts(signal),
      ),
    grapAlerts: (signal) => getJson('/alerts/grap', GrapAlertsSchema, opts(signal)),
    modelHealth: (signal) => getJson('/model-health', ModelHealthSchema, opts(signal)),
    backtest: (signal) => getJson('/backtest', BacktestSchema, opts(signal)),
  }
}

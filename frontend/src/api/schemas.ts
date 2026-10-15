/**
 * The frontend's contract with `GET /api/v1/*`, served by `backend/app/` (models in `backend/app/models.py`,
 * decision in `docs/decisions/0008-api-contract.md`).
 *
 * These schemas are the source of truth for response shapes: the HTTP client validates every response against
 * them and the mock data must satisfy them (api/mock/mock.test.ts). JSON keys are camelCase.
 *
 * What the contract promises, and the UI must keep:
 *  - A forecast is `ok` (a value, plain persistence beside it), `unavailable` (with the reason the forecast job
 *    recorded) or `withheld` (PM2.5 24h). There is never a blank or a substitute number.
 *  - There is no interval and no P(severe): neither is published.
 *  - AQI 1h is a rule (`kind: 'rule'`), AQI 24h is `experimental`.
 */
import { z } from 'zod'
import { POLLUTANT_KEYS } from '@/lib/pollutants'

/** ISO 8601 with an explicit offset, e.g. 2026-10-11T14:00:00+05:30. */
const isoDateTime = z.string().datetime({ offset: true })
const aqiValue = z.number().min(0)

/**
 * Present on every live (non-static) response. `dataAsOf` is the newest observation behind the response (null when
 * the database has no readings), `generatedAt` the server clock, and `stale` means the newest reading is over 3 h old.
 */
const meta = {
  dataAsOf: isoDateTime.nullable(),
  generatedAt: isoDateTime,
  stale: z.boolean(),
}

export const GrapStageSchema = z.enum(['I', 'II', 'III', 'IV'])
export type GrapStage = z.infer<typeof GrapStageSchema>

export const ForecastTargetSchema = z.enum(['aqi', 'pm25'])
export type ForecastTarget = z.infer<typeof ForecastTargetSchema>

export const HorizonSchema = z.enum(['1h', '6h', '24h'])
export type Horizon = z.infer<typeof HorizonSchema>

export const ProductKeySchema = z.enum(['aqi_1h', 'aqi_6h', 'aqi_24h', 'pm25_1h', 'pm25_6h', 'pm25_24h'])
export type ProductKey = z.infer<typeof ProductKeySchema>

/* --------------------------------- forecasts ------------------------------- */

export const ForecastSchema = z
  .object({
    product: ProductKeySchema,
    target: ForecastTargetSchema,
    horizon: HorizonSchema,
    /** "Rule-based (24h-window update)", "Model", "Experimental: about as accurate as assuming no change". */
    label: z.string().min(1),
    kind: z.enum(['rule', 'model']),
    experimental: z.boolean(),
    status: z.enum(['ok', 'unavailable', 'withheld']),
    /** Why there is no forecast; set when `status` is not `ok`. */
    reason: z.string().nullable(),
    issuedAt: isoDateTime.nullable(),
    validAt: isoDateTime.nullable(),
    value: z.number().min(0).nullable(),
    category: z.string().nullable(),
    /** Plain persistence: the current value copied forward, frozen when the forecast was issued. */
    persistence: z.number().min(0).nullable(),
    /** Window-update persistence (AQI only), frozen at issue time. */
    windowUpdate: z.number().min(0).nullable(),
    modelVersion: z.string().nullable(),
  })
  .superRefine((f, ctx) => {
    if (f.status === 'ok' && (f.value === null || f.persistence === null || f.validAt === null)) {
      ctx.addIssue({ code: 'custom', message: 'an ok forecast needs a value, its persistence and a valid-at time' })
    }
    if (f.status !== 'ok' && (f.value !== null || !f.reason)) {
      ctx.addIssue({ code: 'custom', message: 'a forecast without a value must carry a reason and no number' })
    }
  })
export type Forecast = z.infer<typeof ForecastSchema>

/* ---------------------------------- health --------------------------------- */

const JobSchema = z.object({
  job: z.string().min(1),
  status: z.string().min(1),
  lastRunAt: isoDateTime.nullable(),
})
export type Job = z.infer<typeof JobSchema>

export const HealthSchema = z.object({
  ...meta,
  status: z.enum(['ok', 'degraded']),
  newestReadingAt: isoDateTime.nullable(),
  newestForecastAt: isoDateTime.nullable(),
  jobs: z.array(JobSchema),
})
export type Health = z.infer<typeof HealthSchema>

/* --------------------------------- overview -------------------------------- */

const StationBase = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  lat: z.number().min(-90).max(90).nullable(),
  lon: z.number().min(-180).max(180).nullable(),
  /** True when the coordinates are hand-entered rather than published. */
  coordsApproximate: z.boolean(),
})

const CurrentSchema = z.object({
  value: aqiValue,
  category: z.string().nullable(),
  at: isoDateTime,
  /** This station's newest reading is over the stale limit. */
  stale: z.boolean(),
})
export type Current = z.infer<typeof CurrentSchema>

export const OverviewStationSchema = StationBase.extend({
  now: CurrentSchema.nullable(),
  /** The five products, always in the same order; each is ok, unavailable (with a reason) or withheld. */
  forecasts: z.array(ForecastSchema),
})
export type OverviewStation = z.infer<typeof OverviewStationSchema>

export const OverviewSchema = z.object({
  ...meta,
  issuedAt: isoDateTime.nullable(),
  network: z.object({
    stationsWithData: z.number().int().min(0),
    stationsTotal: z.number().int().min(1),
    meanAqiNow: aqiValue.nullable(),
    categoryNow: z.string().nullable(),
    /** Stations with at least one forecast in the latest run. */
    stationsForecast: z.number().int().min(0),
  }),
  stations: z.array(OverviewStationSchema).min(1),
})
export type Overview = z.infer<typeof OverviewSchema>

/* --------------------------------- stations -------------------------------- */

export const StationSummarySchema = StationBase.extend({
  aqiNow: aqiValue.nullable(),
  categoryNow: z.string().nullable(),
  pm25Now: z.number().min(0).nullable(),
  lastReadingAt: isoDateTime.nullable(),
  stale: z.boolean(),
})
export type StationSummary = z.infer<typeof StationSummarySchema>

export const StationsSchema = z.object({
  ...meta,
  stations: z.array(StationSummarySchema).min(1),
})
export type Stations = z.infer<typeof StationsSchema>

const SeriesPointSchema = z.object({ t: isoDateTime, value: z.number() })

const PollutantSchema = z.object({
  key: z.enum(POLLUTANT_KEYS),
  concentration: z.number().min(0),
  unit: z.string(),
})
export type Pollutant = z.infer<typeof PollutantSchema>

const WeatherSchema = z.object({
  temperatureC: z.number().nullable(),
  windMs: z.number().min(0).nullable(),
  humidityPct: z.number().min(0).max(100).nullable(),
  solarWm2: z.number().min(0).nullable(),
})
export type Weather = z.infer<typeof WeatherSchema>

export const StationForecastSchema = z.object({
  ...meta,
  station: z.object({ id: z.string().min(1), name: z.string().min(1) }),
  target: ForecastTargetSchema,
  /** Hourly values for the past 72 h, oldest first; may be empty or have gaps. */
  history: z.array(SeriesPointSchema),
  /** The products for this target: three for AQI; for PM2.5 the 24h one is `withheld`. */
  forecasts: z.array(ForecastSchema),
  pollutants: z.array(PollutantSchema),
  /** `null` for stations without weather sensors (ITO). */
  weather: WeatherSchema.nullable(),
})
export type StationForecast = z.infer<typeof StationForecastSchema>

/* ---------------------------------- alerts --------------------------------- */

export const GrapAlertsSchema = z.object({
  ...meta,
  /** "Indicative only, not an official advisory." Always shown with the stages. */
  disclaimer: z.string().min(1),
  networkMeanAqiNow: aqiValue.nullable(),
  /** The stage the current network mean falls in; null below Stage I or without data. */
  stageIndicatedNow: GrapStageSchema.nullable(),
  /** Stage definitions are served, not hard-coded, so the UI cannot drift from the API. */
  stages: z
    .array(
      z.object({
        stage: GrapStageSchema,
        label: z.string(),
        min: z.number().int(),
        /** `null` for the open-ended top stage. */
        max: z.number().int().nullable(),
        nowCount: z.number().int().min(0),
        forecast6hCount: z.number().int().min(0),
      }),
    )
    .length(4),
  stations: z.array(
    z.object({
      stationId: z.string().min(1),
      name: z.string().min(1),
      now: aqiValue.nullable(),
      stageNow: GrapStageSchema.nullable(),
      forecast6h: aqiValue.nullable(),
      stage6h: GrapStageSchema.nullable(),
      /** Experimental; always shown next to `persistence`. */
      forecast24h: aqiValue.nullable(),
      persistence: aqiValue.nullable(),
    }),
  ),
})
export type GrapAlerts = z.infer<typeof GrapAlertsSchema>

/* ------------------------------- model health ------------------------------ */

const SkillSeriesSchema = z.object({
  product: ProductKeySchema,
  label: z.string(),
  horizon: HorizonSchema,
  target: ForecastTargetSchema,
  /** `YYYY-MM-DD` of each daily rolling-30-day window, oldest first; empty until forecasts have been scored. */
  windowEnd: z.array(z.string()),
  skillVsPersistence: z.array(z.number().nullable()),
  skillVsWindowUpdate: z.array(z.number().nullable()),
  currentVsPersistence: z.number().nullable(),
  currentVsWindowUpdate: z.number().nullable(),
  n: z.number().int().nullable(),
})
export type SkillSeries = z.infer<typeof SkillSeriesSchema>

const LagDaySchema = z.object({
  day: z.string(),
  medianHours: z.number(),
  maxHours: z.number(),
  runs: z.number().int().min(1),
})

/** How far behind the data source is, as seen by every ingest run. */
export const SourceLagSchema = z.object({
  source: z.string().nullable(),
  newestReadingAt: isoDateTime.nullable(),
  currentMedianHours: z.number().nullable(),
  currentMaxHours: z.number().nullable(),
  daily: z.array(LagDaySchema),
})
export type SourceLag = z.infer<typeof SourceLagSchema>

export const ModelHealthSchema = z.object({
  ...meta,
  skill: z.array(SkillSeriesSchema),
  sourceLag: SourceLagSchema,
  /** Share of station-hours with a forecast in the last 24 issue hours. */
  forecastCoverage: z.number().min(0).max(1).nullable(),
  freshness: z.array(
    z.object({
      stationId: z.string().min(1),
      name: z.string().min(1),
      lastReadingAt: isoDateTime.nullable(),
      /** 24 flags, oldest first: was an hourly reading received? */
      hourly: z.array(z.boolean()).length(24),
      note: z.string().nullable(),
    }),
  ),
  jobs: z.array(JobSchema),
  models: z.array(
    z.object({
      version: z.string().min(1),
      name: z.string().min(1),
      target: ForecastTargetSchema,
      horizon: HorizonSchema,
      sha256: z.string(),
    }),
  ),
})
export type ModelHealth = z.infer<typeof ModelHealthSchema>

/* -------------------------------- backtest --------------------------------- */

const EvidenceSchema = z.object({
  product: ProductKeySchema,
  label: z.string(),
  /** "test 2025-11-01..2025-12-31" or "replay 2026-09-01..2026-10-07". */
  window: z.string(),
  n: z.number().int().nullable(),
  skillVsPersistence: z.number(),
  skillVsPersistenceLo: z.number().nullable(),
  skillVsPersistenceHi: z.number().nullable(),
  skillVsWindowUpdate: z.number().nullable(),
  skillVsWindowUpdateLo: z.number().nullable(),
  skillVsWindowUpdateHi: z.number().nullable(),
})
export type Evidence = z.infer<typeof EvidenceSchema>

/** Static, from the report files in the API image; carries no `stale`. */
export const BacktestSchema = z.object({
  note: z.string(),
  evidence: z.array(EvidenceSchema),
})
export type Backtest = z.infer<typeof BacktestSchema>

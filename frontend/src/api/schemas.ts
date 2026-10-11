/**
 * The frontend's contract with `GET /api/v1/*` (docs/TIER_3/PLAN.md section 5).
 *
 * These schemas are the source of truth for response shapes: the HTTP client
 * validates every response against them and the mock data must satisfy them
 * (api/mock/mock.test.ts). JSON keys are camelCase; the FastAPI side should
 * use Pydantic models with `alias_generator=to_camel`.
 */
import { z } from 'zod'
import { POLLUTANT_KEYS } from '@/lib/pollutants'

/** ISO 8601 with an explicit offset, e.g. 2026-10-11T14:00:00+05:30. */
const isoDateTime = z.string().datetime({ offset: true })
const aqiValue = z.number().min(0)
const probability = z.number().min(0).max(1)

/**
 * Present on every live (non-static) response.
 * `dataAsOf` is the newest observation behind the response, `generatedAt` is
 * the server clock when it was built (ages are measured against it, not the
 * browser clock), and `stale` means the newest reading is over 3 h old.
 */
const meta = {
  dataAsOf: isoDateTime,
  generatedAt: isoDateTime,
  stale: z.boolean(),
}

export const GrapStageSchema = z.enum(['I', 'II', 'III', 'IV'])
export type GrapStage = z.infer<typeof GrapStageSchema>

export const ForecastTargetSchema = z.enum(['aqi', 'pm25'])
export type ForecastTarget = z.infer<typeof ForecastTargetSchema>

export const HorizonSchema = z.enum(['1h', '6h', '24h'])
export type Horizon = z.infer<typeof HorizonSchema>

/* ---------------------------------- health --------------------------------- */

export const HealthSchema = z.object({
  ...meta,
  status: z.enum(['ok', 'degraded']),
})
export type Health = z.infer<typeof HealthSchema>

/* --------------------------------- overview -------------------------------- */

const StationBase = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  /** Compass area of Delhi, e.g. "North-west". */
  area: z.string(),
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  /** True when the coordinates are hand-entered rather than published. */
  coordsApproximate: z.boolean(),
})

export const OverviewStationSchema = StationBase.extend({
  now: aqiValue,
  forecast24h: aqiValue,
  /** 80% interval for the 24h forecast. */
  lo: aqiValue,
  hi: aqiValue,
  pSevere: probability,
})
export type OverviewStation = z.infer<typeof OverviewStationSchema>

export const OverviewSchema = z.object({
  ...meta,
  issuedAt: isoDateTime,
  /** The moment the 24h forecast is for. */
  validFor: isoDateTime,
  network: z.object({
    now: aqiValue,
    forecast24h: aqiValue,
    lo: aqiValue,
    hi: aqiValue,
    pSevere: probability,
  }),
  grapStageInForce: GrapStageSchema.nullable(),
  stations: z.array(OverviewStationSchema).min(1),
})
export type Overview = z.infer<typeof OverviewSchema>

/* --------------------------------- stations -------------------------------- */

export const StationSummarySchema = StationBase.extend({
  aqiNow: aqiValue,
  pm25Now: z.number().min(0).nullable(),
})
export type StationSummary = z.infer<typeof StationSummarySchema>

export const StationsSchema = z.object({
  ...meta,
  stations: z.array(StationSummarySchema).min(1),
})
export type Stations = z.infer<typeof StationsSchema>

const SeriesPointSchema = z.object({ t: isoDateTime, value: z.number() })

const ForecastPointSchema = z.object({
  t: isoDateTime,
  median: z.number(),
  lo: z.number(),
  hi: z.number(),
})

const HorizonForecastSchema = z.object({
  horizon: HorizonSchema,
  validAt: isoDateTime,
  /** `null` when the model is withheld for this horizon (24h PM2.5 never ships). */
  value: z.number().nullable(),
  lo: z.number().nullable(),
  hi: z.number().nullable(),
  /** Backtest skill vs copy-last: 1 - model MAE / copy-last MAE. */
  backtestSkill: z.number(),
})
export type HorizonForecast = z.infer<typeof HorizonForecastSchema>

const PollutantSchema = z.object({
  key: z.enum(POLLUTANT_KEYS),
  concentration: z.number().min(0),
  unit: z.string(),
  /** CPCB sub-index (0-500 scale). */
  subIndex: z.number().min(0),
})
export type Pollutant = z.infer<typeof PollutantSchema>

const WeatherSchema = z.object({
  temperatureC: z.number(),
  windMs: z.number().min(0),
  humidityPct: z.number().min(0).max(100),
  solarWm2: z.number().min(0),
})
export type Weather = z.infer<typeof WeatherSchema>

export const StationForecastSchema = z.object({
  ...meta,
  station: z.object({ id: z.string().min(1), name: z.string().min(1), area: z.string() }),
  target: ForecastTargetSchema,
  /** Hourly values from 72 h ago to "now" (73 points), oldest first. */
  history: z.array(SeriesPointSchema).min(2),
  /** Hourly median and 80% band from "now" (hour 0) to the horizon end. */
  forecast: z.array(ForecastPointSchema).min(2),
  horizons: z.array(HorizonForecastSchema).length(3),
  pollutants: z.array(PollutantSchema),
  /** `null` for stations without weather sensors (ITO). */
  weather: WeatherSchema.nullable(),
})
export type StationForecast = z.infer<typeof StationForecastSchema>

/* ---------------------------------- alerts --------------------------------- */

export const AlertStatusSchema = z.enum(['active', 'new', 'watch'])
export type AlertStatus = z.infer<typeof AlertStatusSchema>

export const GrapAlertsSchema = z.object({
  ...meta,
  stageInForce: GrapStageSchema.nullable(),
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
        tomorrowCount: z.number().int().min(0),
      }),
    )
    .length(4),
  /** Stations with a meaningful chance of Severe in the next 24 h. */
  alerts: z.array(
    z.object({
      stationId: z.string().min(1),
      name: z.string().min(1),
      validFor: isoDateTime,
      forecast24h: aqiValue,
      lo: aqiValue,
      hi: aqiValue,
      pSevere: probability,
      /** What copy-last would say: the current AQI. */
      persistence: aqiValue,
      status: AlertStatusSchema,
    }),
  ),
  /** Minimum P(Severe) for a station to be listed. */
  alertMinProbability: probability,
})
export type GrapAlerts = z.infer<typeof GrapAlertsSchema>

/* ------------------------------- model health ------------------------------ */

export const SkillSeriesIdSchema = z.enum(['aqi24', 'pm25_6', 'aqi1'])
export type SkillSeriesId = z.infer<typeof SkillSeriesIdSchema>

export const ModelHealthSchema = z.object({
  ...meta,
  skill: z
    .array(
      z.object({
        id: SkillSeriesIdSchema,
        /** Last 30 daily rolling-30-day skill values, oldest first. */
        series: z.array(z.number()).min(2),
        current: z.number(),
        /** Backtest reference, formatted by the API, e.g. "+0.10 / +0.11 (winters 24, 25)". */
        referenceLabel: z.string(),
      }),
    )
    .length(3),
  calibration: z.object({
    coverage80: probability,
    brierModel: z.number().min(0),
    brierPersistence: z.number().min(0),
    /** Share of the last 30 days' hours at AQI 401 or more. */
    severeShare30d: probability,
  }),
  freshness: z.array(
    z.object({
      stationId: z.string().min(1),
      name: z.string().min(1),
      lastReadingAt: isoDateTime,
      /** 24 flags, oldest first: was an hourly reading received? */
      hourly: z.array(z.boolean()).length(24),
      note: z.string().nullable(),
    }),
  ),
  jobs: z.array(
    z.object({
      id: z.string().min(1),
      name: z.string().min(1),
      schedule: z.string(),
      lastRunAt: isoDateTime,
      status: z.enum(['ok', 'retry', 'failed']),
    }),
  ),
  models: z.array(
    z.object({ name: z.string().min(1), description: z.string(), version: z.string().min(1) }),
  ),
})
export type ModelHealth = z.infer<typeof ModelHealthSchema>

/* -------------------------------- backtest --------------------------------- */

const AlertRuleSchema = z.object({
  id: z.enum(['cpcb', 'costAware']),
  /** AQI at or above which the rule alerts. */
  threshold: aqiValue,
  recall: probability,
  precision: probability,
  falsePositiveRate: probability,
  missedHours: z.number().int().min(0),
})
export type AlertRule = z.infer<typeof AlertRuleSchema>

const LeadTimeSchema = z.object({
  horizon: z.enum(['24h', '6h']),
  episodes: z.number().int().min(0),
  modelDetectionRate: probability,
  persistenceDetectionRate: probability,
  modelLeadHours: z.number().min(0),
  persistenceLeadHours: z.number().min(0),
})
export type LeadTime = z.infer<typeof LeadTimeSchema>

/** Static, from `reports/metrics/headline_metrics.csv`; carries no `stale`. */
export const BacktestSchema = z.object({
  /** Number of past winters scored. */
  winters: z.number().int().min(1),
  /** 24h AQI MAE skill vs copy-last, averaged over the scored winters. */
  skill24h: z.number(),
  /** Share of winter days inside the 80% range. */
  coverage80: probability,
  brierModel: z.number().min(0),
  brierPersistence: z.number().min(0),
  severeShare: z.object({ validation: probability, winter: probability }),
  alertRules: z.array(AlertRuleSchema).min(1),
  leadTimes: z.array(LeadTimeSchema),
})
export type Backtest = z.infer<typeof BacktestSchema>

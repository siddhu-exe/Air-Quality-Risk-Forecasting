/**
 * Sample data served while the live API does not exist (VITE_USE_MOCK=true).
 * Values are those shown in the design (docs/design/); coordinates are the
 * real CPCB station coordinates from src/live/load_stations.py. Every export
 * is validated against the API schemas in mock.test.ts.
 */
import type {
  Backtest,
  ForecastTarget,
  GrapAlerts,
  Health,
  ModelHealth,
  Overview,
  Pollutant,
  StationForecast,
  Stations,
} from '../schemas'

const HOUR = 3_600_000
const MINUTE = 60_000

/** Newest observation: Sun 11 Oct 2026, 14:00 IST. */
const DATA_AS_OF = '2026-10-11T14:00:00+05:30'
/** Server clock: 14 minutes later. */
const GENERATED_AT = '2026-10-11T14:14:00+05:30'

const asOfMs = Date.parse(DATA_AS_OF)
const iso = (ms: number): string => new Date(ms).toISOString()
const atHours = (h: number): string => iso(asOfMs + h * HOUR)

const meta = { dataAsOf: DATA_AS_OF, generatedAt: GENERATED_AT, stale: false }

interface RawStation {
  id: string
  name: string
  area: string
  lat: number
  lon: number
  now: number
  f1: number
  f6: number
  f24: number
  lo: number
  hi: number
  pm: number
  pm1: number
  pm6: number
  pSevere: number
  hasMet: boolean
  /** AQI points gained over the past 72 h (drives the sample history). */
  trend: number
}

const RAW: readonly RawStation[] = [
  { id: 'bawana', name: 'Bawana', area: 'North-west', lat: 28.7762, lon: 77.05107, now: 401, f1: 402, f6: 408, f24: 418, lo: 365, hi: 475, pm: 268, pm1: 255, pm6: 231, pSevere: 0.63, hasMet: true, trend: 60 },
  { id: 'anand-vihar', name: 'Anand Vihar', area: 'East', lat: 28.64683, lon: 77.31603, now: 388, f1: 389, f6: 396, f24: 412, lo: 360, hi: 470, pm: 241, pm1: 236, pm6: 214, pSevere: 0.58, hasMet: true, trend: 70 },
  { id: 'jahangirpuri', name: 'Jahangirpuri', area: 'North', lat: 28.73282, lon: 77.17063, now: 372, f1: 373, f6: 380, f24: 395, lo: 342, hi: 452, pm: 226, pm1: 219, pm6: 205, pSevere: 0.46, hasMet: true, trend: 55 },
  { id: 'punjabi-bagh', name: 'Punjabi Bagh', area: 'West', lat: 28.67404, lon: 77.13102, now: 349, f1: 350, f6: 355, f24: 366, lo: 314, hi: 424, pm: 198, pm1: 194, pm6: 181, pSevere: 0.34, hasMet: true, trend: 45 },
  { id: 'dwarka-sec-8', name: 'Dwarka Sec-8', area: 'South-west', lat: 28.57103, lon: 77.0719, now: 336, f1: 337, f6: 342, f24: 352, lo: 300, hi: 410, pm: 187, pm1: 183, pm6: 170, pSevere: 0.29, hasMet: true, trend: 40 },
  { id: 'r-k-puram', name: 'R K Puram', area: 'South', lat: 28.56326, lon: 77.18694, now: 327, f1: 328, f6: 332, f24: 341, lo: 290, hi: 398, pm: 176, pm1: 171, pm6: 162, pSevere: 0.24, hasMet: true, trend: 38 },
  { id: 'ito', name: 'ITO', area: 'Central', lat: 28.62862, lon: 77.24106, now: 318, f1: 319, f6: 324, f24: 335, lo: 285, hi: 392, pm: 169, pm1: 166, pm6: 154, pSevere: 0.21, hasMet: false, trend: 35 },
]

/* --------------------------------- health ---------------------------------- */

export const healthFixture: Health = { ...meta, status: 'ok' }

/* -------------------------------- overview --------------------------------- */

export const overviewFixture: Overview = {
  ...meta,
  issuedAt: DATA_AS_OF,
  validFor: atHours(24),
  network: { now: 356, forecast24h: 374, lo: 325, hi: 431, pSevere: 0.31 },
  grapStageInForce: 'II',
  stations: RAW.map((s) => ({
    id: s.id,
    name: s.name,
    area: s.area,
    lat: s.lat,
    lon: s.lon,
    coordsApproximate: false,
    now: s.now,
    forecast24h: s.f24,
    lo: s.lo,
    hi: s.hi,
    pSevere: s.pSevere,
  })),
}

/* -------------------------------- stations --------------------------------- */

export const stationsFixture: Stations = {
  ...meta,
  stations: RAW.map((s) => ({
    id: s.id,
    name: s.name,
    area: s.area,
    lat: s.lat,
    lon: s.lon,
    coordsApproximate: false,
    aqiNow: s.now,
    pm25Now: s.pm,
  })),
}

/** CPCB PM2.5 sub-index (piecewise linear), used only to fill the sample table. */
function pm25SubIndex(pm: number): number {
  if (pm <= 60) return (pm * 100) / 60
  if (pm <= 90) return 100 + ((pm - 60) * 100) / 30
  if (pm <= 120) return 200 + ((pm - 90) * 100) / 30
  if (pm <= 250) return 300 + ((pm - 120) * 100) / 130
  return 400 + ((pm - 250) * 100) / 250
}

function pollutantsFor(s: RawStation): Pollutant[] {
  return [
    { key: 'pm25', concentration: s.pm, unit: 'µg/m³', subIndex: Math.round(pm25SubIndex(s.pm)) },
    { key: 'pm10', concentration: Math.round(s.pm * 1.7), unit: 'µg/m³', subIndex: Math.round(s.now * 0.78) },
    { key: 'no2', concentration: 64, unit: 'µg/m³', subIndex: 80 },
    { key: 'co', concentration: 1.9, unit: 'mg/m³', subIndex: 95 },
    { key: 'o3', concentration: 38, unit: 'µg/m³', subIndex: 38 },
    { key: 'so2', concentration: 14, unit: 'µg/m³', subIndex: 18 },
  ]
}

/** Deterministic past-72h curve and forecast ramp, mirroring the design's sample chart. */
export function stationForecastFixture(id: string, target: ForecastTarget): StationForecast | undefined {
  const s = RAW.find((r) => r.id === id)
  if (!s) return undefined

  const isPm = target === 'pm25'
  const now = isPm ? s.pm : s.now
  const amp = isPm ? 70 : 12
  const trend = isPm ? s.trend * 0.8 : s.trend
  const history = Array.from({ length: 73 }, (_, i) => {
    const k = 72 - i
    const wave = amp * Math.sin(k / (isPm ? 3.8 : 7)) * (isPm ? 1 : k / 72)
    return { t: atHours(-k), value: Math.round((now - (trend * k) / 72 + wave) * 10) / 10 }
  })

  const steps = isPm ? 6 : 24
  const end = isPm ? s.pm6 : s.f24
  const spreadLo = isPm ? 40 : s.f24 - s.lo
  const spreadHi = isPm ? 48 : s.hi - s.f24
  const forecast = Array.from({ length: steps + 1 }, (_, j) => {
    const median = now + ((end - now) * j) / steps
    const r = j / steps
    return {
      t: atHours(j),
      median: Math.round(median * 10) / 10,
      lo: Math.round((median - spreadLo * r) * 10) / 10,
      hi: Math.round((median + spreadHi * r) * 10) / 10,
    }
  })

  const horizons: StationForecast['horizons'] = isPm
    ? [
        { horizon: '1h', validAt: atHours(1), value: s.pm1, lo: null, hi: null, backtestSkill: 0.201 },
        { horizon: '6h', validAt: atHours(6), value: s.pm6, lo: null, hi: null, backtestSkill: 0.374 },
        { horizon: '24h', validAt: atHours(24), value: null, lo: null, hi: null, backtestSkill: -0.093 },
      ]
    : [
        { horizon: '1h', validAt: atHours(1), value: s.f1, lo: null, hi: null, backtestSkill: 0.01 },
        { horizon: '6h', validAt: atHours(6), value: s.f6, lo: null, hi: null, backtestSkill: 0.069 },
        { horizon: '24h', validAt: atHours(24), value: s.f24, lo: s.lo, hi: s.hi, backtestSkill: 0.11 },
      ]

  return {
    ...meta,
    station: { id: s.id, name: s.name, area: s.area },
    target,
    history,
    forecast,
    horizons,
    pollutants: pollutantsFor(s),
    weather: s.hasMet ? { temperatureC: 19.4, windMs: 0.8, humidityPct: 71, solarWm2: 212 } : null,
  }
}

/* --------------------------------- alerts ---------------------------------- */

export const grapAlertsFixture: GrapAlerts = {
  ...meta,
  stageInForce: 'II',
  alertMinProbability: 0.3,
  stages: [
    { stage: 'I', label: 'Poor', min: 201, max: 300, nowCount: 0, tomorrowCount: 0 },
    { stage: 'II', label: 'Very Poor', min: 301, max: 400, nowCount: 6, tomorrowCount: 5 },
    { stage: 'III', label: 'Severe', min: 401, max: 450, nowCount: 1, tomorrowCount: 2 },
    { stage: 'IV', label: 'Severe+', min: 451, max: null, nowCount: 0, tomorrowCount: 0 },
  ],
  alerts: [
    { stationId: 'bawana', name: 'Bawana', validFor: atHours(24), forecast24h: 418, lo: 365, hi: 475, pSevere: 0.63, persistence: 401, status: 'active' },
    { stationId: 'anand-vihar', name: 'Anand Vihar', validFor: atHours(24), forecast24h: 412, lo: 360, hi: 470, pSevere: 0.58, persistence: 388, status: 'new' },
    { stationId: 'jahangirpuri', name: 'Jahangirpuri', validFor: atHours(24), forecast24h: 395, lo: 342, hi: 452, pSevere: 0.46, persistence: 372, status: 'watch' },
    { stationId: 'punjabi-bagh', name: 'Punjabi Bagh', validFor: atHours(24), forecast24h: 366, lo: 314, hi: 424, pSevere: 0.34, persistence: 349, status: 'watch' },
  ],
}

/* ------------------------------- model health ------------------------------ */

function skillSeries(base: number, amp: number, seed: number): number[] {
  return Array.from({ length: 30 }, (_, i) => {
    const v = base + amp * Math.sin(i / 3.1 + seed) + amp * 0.5 * Math.sin(i / 1.3 + seed * 2)
    return Math.round(v * 1000) / 1000
  })
}

function hourlyFlags(gaps: readonly number[]): boolean[] {
  return Array.from({ length: 24 }, (_, i) => !gaps.includes(i))
}

const minutesAgo = (m: number): string => iso(Date.parse(GENERATED_AT) - m * MINUTE)

export const modelHealthFixture: ModelHealth = {
  ...meta,
  skill: [
    { id: 'aqi24', series: skillSeries(0.09, 0.035, 0.4), current: 0.09, referenceLabel: '+0.10 / +0.11 (winters 24, 25)' },
    { id: 'pm25_6', series: skillSeries(0.21, 0.05, 1.7), current: 0.21, referenceLabel: '+0.37 (winter 25)' },
    { id: 'aqi1', series: skillSeries(0.01, 0.03, 2.9), current: 0.01, referenceLabel: '+0.05 MAE, −0.33 RMSE' },
  ],
  calibration: { coverage80: 0.78, brierModel: 0.187, brierPersistence: 0.191, severeShare30d: 0.12 },
  freshness: [
    { stationId: 'anand-vihar', name: 'Anand Vihar', lastReadingAt: minutesAgo(14), hourly: hourlyFlags([]), note: null },
    { stationId: 'bawana', name: 'Bawana', lastReadingAt: minutesAgo(14), hourly: hourlyFlags([9]), note: '1 hour missing' },
    { stationId: 'dwarka-sec-8', name: 'Dwarka Sec-8', lastReadingAt: minutesAgo(14), hourly: hourlyFlags([]), note: null },
    { stationId: 'ito', name: 'ITO', lastReadingAt: minutesAgo(14), hourly: hourlyFlags([]), note: 'No weather sensors' },
    { stationId: 'jahangirpuri', name: 'Jahangirpuri', lastReadingAt: minutesAgo(134), hourly: hourlyFlags([22, 23]), note: 'Feed delayed; forecast uses neighbours' },
    { stationId: 'punjabi-bagh', name: 'Punjabi Bagh', lastReadingAt: minutesAgo(14), hourly: hourlyFlags([]), note: null },
    { stationId: 'r-k-puram', name: 'R K Puram', lastReadingAt: minutesAgo(14), hourly: hourlyFlags([3, 4, 5]), note: '3 hours missing overnight' },
  ],
  jobs: [
    { id: 'ingest', name: 'Ingest CPCB readings', schedule: 'Every hour at :10', lastRunAt: '2026-10-11T14:10:00+05:30', status: 'ok' },
    { id: 'forecast', name: 'Issue forecasts', schedule: 'Hourly, 1h / 6h / 24h', lastRunAt: '2026-10-11T14:12:00+05:30', status: 'ok' },
    { id: 'score', name: 'Score vs actuals', schedule: 'Nightly at 02:00', lastRunAt: '2026-10-11T02:04:00+05:30', status: 'ok' },
    { id: 'weather', name: 'Weather pull (Open-Meteo)', schedule: 'Every 6 hours', lastRunAt: '2026-10-11T12:00:00+05:30', status: 'retry' },
  ],
  models: [
    { name: 'AQI 24h', description: '50/50 copy-last + Ridge, 49 features', version: 'aqi24-6c' },
    { name: 'AQI 1h / 6h', description: 'Gradient-boosted trees', version: 'aqi-gbm-v1' },
    { name: 'PM2.5 1h / 6h', description: 'Gradient boosting on the change', version: 'pm25-t23' },
    { name: 'Range & P(Severe)', description: 'Quantile model + conformal pad', version: 'q-t25' },
  ],
}

/* -------------------------------- backtest --------------------------------- */

export const backtestFixture: Backtest = {
  winters: 2,
  skill24h: 0.11,
  coverage80: 0.76,
  brierModel: 0.194,
  brierPersistence: 0.196,
  severeShare: { validation: 0.02, winter: 0.41 },
  alertRules: [
    { id: 'cpcb', threshold: 401, recall: 0.61, precision: 0.74, falsePositiveRate: 0.15, missedHours: 1568 },
    { id: 'costAware', threshold: 275, recall: 0.998, precision: 0.43, falsePositiveRate: 0.93, missedHours: 7 },
  ],
  leadTimes: [
    { horizon: '24h', episodes: 86, modelDetectionRate: 0.698, persistenceDetectionRate: 0.651, modelLeadHours: 7.4, persistenceLeadHours: 5.0 },
    { horizon: '6h', episodes: 87, modelDetectionRate: 0.839, persistenceDetectionRate: 0.931, modelLeadHours: 2.5, persistenceLeadHours: 0.5 },
  ],
}

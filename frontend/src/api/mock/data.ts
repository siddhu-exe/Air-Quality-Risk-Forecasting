/**
 * Sample data served while the live API is not used (VITE_USE_MOCK=true).
 *
 * It shows the states the real API produces, not just the happy path: one station with a stale feed (every product
 * unavailable, with the job's reason), one with PM2.5 dropped, one with the 1h rule unavailable, and the PM2.5 24h
 * forecast withheld. Station ids and names are the API's. Coordinates are the project's approximate station
 * coordinates. Every export is validated against the API schemas in mock.test.ts.
 */
import { categoryOf } from '@/lib/aqi'
import type {
  Backtest,
  Forecast,
  ForecastTarget,
  GrapAlerts,
  GrapStage,
  Health,
  ModelHealth,
  Overview,
  Pollutant,
  ProductKey,
  StationForecast,
  Stations,
} from '../schemas'

const HOUR = 3_600_000
const MINUTE = 60_000

/** Newest observation: Thu 15 Oct 2026, 14:00 IST (the hour label; the reading covers 14:00 to 15:00). */
const DATA_AS_OF = '2026-10-15T14:00:00+05:30'
/** Server clock: 35 minutes after the hour ended. */
const GENERATED_AT = '2026-10-15T15:35:00+05:30'
const ISSUED_AT = '2026-10-15T14:00:00+05:30'

const asOfMs = Date.parse(DATA_AS_OF)
const iso = (ms: number): string => new Date(ms).toISOString()
const atHours = (h: number): string => iso(asOfMs + h * HOUR)

const meta = { dataAsOf: DATA_AS_OF, generatedAt: GENERATED_AT, stale: false }

export const STALE_REASON = 'stale: newest reading is 4.6 h older than the issue hour (limit 3 h)'
export const DROPPED_PM25_REASON = 'no current pm25 value at the issue hour'
export const NO_RULE_REASON = 'no valid current hourly AQI, or fewer than 16 valid hours in the 24h window'

interface RawStation {
  id: string
  name: string
  lat: number
  lon: number
  now: number
  a1: number
  a6: number
  a24: number
  wu6: number
  wu24: number
  pm: number
  pm1: number
  pm6: number
  hasMet: boolean
  /** AQI points gained over the past 72 h (drives the sample history). */
  trend: number
  /** Every product is unavailable because the station's feed is stale. */
  stale?: boolean
  /** PM2.5 products dropped: no current PM2.5 reading. */
  noPm25?: boolean
  /** The 1h rule is unavailable. */
  noRule?: boolean
}

const RAW: readonly RawStation[] = [
  { id: '4', name: 'Bawana', lat: 28.7762, lon: 77.05107, now: 331, a1: 332, a6: 338, a24: 345, wu6: 334, wu24: 322, pm: 168, pm1: 172, pm6: 181, hasMet: true, trend: 40 },
  { id: '3', name: 'Anand Vihar', lat: 28.64683, lon: 77.31603, now: 318, a1: 319, a6: 325, a24: 331, wu6: 321, wu24: 305, pm: 154, pm1: 158, pm6: 166, hasMet: true, trend: 48 },
  { id: '7', name: 'Jahangirpuri', lat: 28.73282, lon: 77.17063, now: 301, a1: 0, a6: 0, a24: 0, wu6: 0, wu24: 0, pm: 0, pm1: 0, pm6: 0, hasMet: true, trend: 30, stale: true },
  { id: '8', name: 'Punjabi Bagh', lat: 28.67404, lon: 77.13102, now: 289, a1: 290, a6: 296, a24: 300, wu6: 291, wu24: 281, pm: 139, pm1: 141, pm6: 150, hasMet: true, trend: 28 },
  { id: '5', name: 'Dwarka-Sector 8', lat: 28.57103, lon: 77.0719, now: 276, a1: 277, a6: 281, a24: 286, wu6: 278, wu24: 270, pm: 0, pm1: 0, pm6: 0, hasMet: true, trend: 24, noPm25: true },
  { id: '9', name: 'R K Puram', lat: 28.56326, lon: 77.18694, now: 262, a1: 263, a6: 268, a24: 271, wu6: 264, wu24: 255, pm: 121, pm1: 124, pm6: 131, hasMet: true, trend: 21 },
  { id: '6', name: 'ITO', lat: 28.62862, lon: 77.24106, now: 249, a1: 0, a6: 255, a24: 259, wu6: 251, wu24: 243, pm: 113, pm1: 115, pm6: 120, hasMet: false, trend: 18, noRule: true },
]

/* -------------------------------- forecasts -------------------------------- */

const LABEL_RULE = 'Rule-based (24h-window update)'
const LABEL_MODEL = 'Model'
const LABEL_EXPERIMENTAL = 'Experimental: about as accurate as assuming no change'
const PM25_24H_REASON = 'No 24h PM2.5 forecast is published: it does not beat persistence.'

const PRODUCT_META: Record<ProductKey, { target: ForecastTarget; horizon: '1h' | '6h' | '24h'; hours: number; label: string; kind: 'rule' | 'model'; experimental: boolean }> = {
  aqi_1h: { target: 'aqi', horizon: '1h', hours: 1, label: LABEL_RULE, kind: 'rule', experimental: false },
  aqi_6h: { target: 'aqi', horizon: '6h', hours: 6, label: LABEL_MODEL, kind: 'model', experimental: false },
  aqi_24h: { target: 'aqi', horizon: '24h', hours: 24, label: LABEL_EXPERIMENTAL, kind: 'model', experimental: true },
  pm25_1h: { target: 'pm25', horizon: '1h', hours: 1, label: LABEL_MODEL, kind: 'model', experimental: false },
  pm25_6h: { target: 'pm25', horizon: '6h', hours: 6, label: LABEL_MODEL, kind: 'model', experimental: false },
  pm25_24h: { target: 'pm25', horizon: '24h', hours: 24, label: 'Not published', kind: 'model', experimental: false },
}

const VERSIONS: Record<ProductKey, string> = {
  aqi_1h: 'aqi-1h-window-update-v1',
  aqi_6h: 'aqi-6h-lgb-live-v1',
  aqi_24h: 'aqi-24h-hybrid-live-v1',
  pm25_1h: 'pm25-1h-hgb-live-v1',
  pm25_6h: 'pm25-6h-hgb-live-v1',
  pm25_24h: 'none',
}

/** A forecast of any status; the helper keeps fixtures and tests from re-spelling the full shape. */
export function makeForecast(
  product: ProductKey,
  status: Forecast['status'],
  fields: {
    value?: number
    persistence?: number
    windowUpdate?: number
    reason?: string
    lastIssued?: Forecast['lastIssued']
  } = {},
): Forecast {
  const m = PRODUCT_META[product]
  const ok = status === 'ok'
  const value = ok ? (fields.value ?? 100) : null
  return {
    product,
    target: m.target,
    horizon: m.horizon,
    label: m.label,
    kind: m.kind,
    experimental: m.experimental,
    status,
    reason: ok ? null : (fields.reason ?? 'no forecast was issued for this product in the latest run'),
    issuedAt: ok ? ISSUED_AT : null,
    validAt: ok ? atHours(m.hours) : null,
    value,
    category: ok && m.target === 'aqi' && value !== null ? categoryOf(value).label : null,
    persistence: ok ? (fields.persistence ?? value) : null,
    windowUpdate: ok && m.target === 'aqi' ? (fields.windowUpdate ?? fields.value ?? value) : null,
    modelVersion: ok ? VERSIONS[product] : null,
    lastIssued: ok ? null : (fields.lastIssued ?? null),
  }
}

function forecastsFor(s: RawStation, products: readonly ProductKey[]): Forecast[] {
  return products.map((product): Forecast => {
    if (product === 'pm25_24h') return makeForecast(product, 'withheld', { reason: PM25_24H_REASON })
    if (s.stale) return makeForecast(product, 'unavailable', { reason: STALE_REASON })
    if (s.noPm25 && product.startsWith('pm25')) return makeForecast(product, 'unavailable', { reason: DROPPED_PM25_REASON })
    if (s.noRule && product === 'aqi_1h') return makeForecast(product, 'unavailable', { reason: NO_RULE_REASON })
    switch (product) {
      case 'aqi_1h':
        return makeForecast(product, 'ok', { value: s.a1, persistence: s.now, windowUpdate: s.a1 })
      case 'aqi_6h':
        return makeForecast(product, 'ok', { value: s.a6, persistence: s.now, windowUpdate: s.wu6 })
      case 'aqi_24h':
        return makeForecast(product, 'ok', { value: s.a24, persistence: s.now, windowUpdate: s.wu24 })
      case 'pm25_1h':
        return makeForecast(product, 'ok', { value: s.pm1, persistence: s.pm })
      default:
        return makeForecast(product, 'ok', { value: s.pm6, persistence: s.pm })
    }
  })
}

const OVERVIEW_PRODUCTS: readonly ProductKey[] = ['aqi_1h', 'aqi_6h', 'aqi_24h', 'pm25_1h', 'pm25_6h']

const nowOf = (s: RawStation, staleHours = 0) => ({
  value: s.now,
  category: categoryOf(s.now).label,
  at: s.stale ? atHours(-5) : DATA_AS_OF,
  stale: staleHours > 3 || Boolean(s.stale),
})

const base = (s: RawStation) => ({
  id: s.id,
  name: s.name,
  lat: s.lat,
  lon: s.lon,
  coordsApproximate: true,
})

const fresh = RAW.filter((s) => !s.stale)
const meanNow = Math.round((fresh.reduce((sum, s) => sum + s.now, 0) / fresh.length) * 10) / 10

/* --------------------------------- health ---------------------------------- */

export const healthFixture: Health = {
  ...meta,
  status: 'ok',
  newestReadingAt: DATA_AS_OF,
  newestForecastAt: ISSUED_AT,
  jobs: [
    { job: 'ingest', status: 'success', lastRunAt: '2026-10-15T15:10:00+05:30' },
    { job: 'forecast', status: 'success', lastRunAt: '2026-10-15T15:12:00+05:30' },
  ],
}

/* -------------------------------- overview --------------------------------- */

export const overviewFixture: Overview = {
  ...meta,
  issuedAt: ISSUED_AT,
  network: {
    stationsWithData: fresh.length,
    stationsTotal: RAW.length,
    meanAqiNow: meanNow,
    categoryNow: categoryOf(meanNow).label,
    stationsForecast: fresh.length,
  },
  stations: RAW.map((s) => ({
    ...base(s),
    now: nowOf(s, s.stale ? 4.6 : 0),
    forecasts: forecastsFor(s, OVERVIEW_PRODUCTS),
  })),
}

/* -------------------------------- stations --------------------------------- */

export const stationsFixture: Stations = {
  ...meta,
  stations: RAW.map((s) => ({
    ...base(s),
    aqiNow: s.now,
    categoryNow: categoryOf(s.now).label,
    pm25Now: s.noPm25 || s.stale ? null : s.pm,
    lastReadingAt: s.stale ? atHours(-5) : DATA_AS_OF,
    stale: Boolean(s.stale),
  })),
}

function pollutantsFor(s: RawStation): Pollutant[] {
  if (s.stale) return []
  const pm = s.noPm25 ? [] : [{ key: 'pm25' as const, concentration: s.pm, unit: 'µg/m³' }]
  return [
    ...pm,
    { key: 'pm10', concentration: Math.round(s.now * 0.62), unit: 'µg/m³' },
    { key: 'no2', concentration: 64, unit: 'µg/m³' },
    { key: 'co', concentration: 1.9, unit: 'mg/m³' },
    { key: 'o3', concentration: 38, unit: 'µg/m³' },
    { key: 'so2', concentration: 14, unit: 'µg/m³' },
  ]
}

/** Deterministic past-72h curve for one station and measure. */
export function stationForecastFixture(id: string, target: ForecastTarget): StationForecast | undefined {
  const s = RAW.find((r) => r.id === id)
  if (!s) return undefined

  const isPm = target === 'pm25'
  const products: ProductKey[] = isPm ? ['pm25_1h', 'pm25_6h', 'pm25_24h'] : ['aqi_1h', 'aqi_6h', 'aqi_24h']
  const now = isPm ? s.pm : s.now
  const amp = isPm ? 40 : 10
  const trend = isPm ? s.trend * 0.8 : s.trend
  // A station with no current PM2.5 (or a stale feed) has a short, gappy history instead of a full one.
  const missing = (isPm && s.noPm25) || s.stale
  const history = missing
    ? []
    : Array.from({ length: 73 }, (_, i) => {
        const k = 72 - i
        const wave = amp * Math.sin(k / (isPm ? 3.8 : 7)) * (isPm ? 1 : k / 72)
        return { t: atHours(-k), value: Math.max(0, Math.round((now - (trend * k) / 72 + wave) * 10) / 10) }
      })

  return {
    ...meta,
    station: { id: s.id, name: s.name },
    target,
    history,
    forecasts: forecastsFor(s, products),
    pollutants: pollutantsFor(s),
    weather: s.hasMet && !s.stale ? { temperatureC: 26.4, windMs: 1.4, humidityPct: 48, solarWm2: 312 } : null,
  }
}

/* --------------------------------- alerts ---------------------------------- */

const stageOf = (aqi: number): GrapStage | null => {
  const v = Math.round(aqi)
  if (v >= 451) return 'IV'
  if (v >= 401) return 'III'
  if (v >= 301) return 'II'
  if (v >= 201) return 'I'
  return null
}

const STAGES = [
  { stage: 'I', label: 'Poor', min: 201, max: 300 },
  { stage: 'II', label: 'Very Poor', min: 301, max: 400 },
  { stage: 'III', label: 'Severe', min: 401, max: 450 },
  { stage: 'IV', label: 'Severe+', min: 451, max: null },
] as const

const grapRows = RAW.map((s) => ({
  stationId: s.id,
  name: s.name,
  now: s.stale ? null : s.now,
  stageNow: s.stale ? null : stageOf(s.now),
  forecast6h: s.stale ? null : s.a6 || null,
  stage6h: s.stale || !s.a6 ? null : stageOf(s.a6),
  forecast24h: s.stale ? null : s.a24,
  persistence: s.stale ? null : s.now,
}))

export const grapAlertsFixture: GrapAlerts = {
  ...meta,
  disclaimer:
    'Indicative only, not an official advisory. Stages follow the CAQM GRAP bands (to be re-verified before launch); the 24h forecast is experimental.',
  networkMeanAqiNow: meanNow,
  stageIndicatedNow: stageOf(meanNow),
  stages: STAGES.map((st) => ({
    ...st,
    nowCount: grapRows.filter((r) => r.stageNow === st.stage).length,
    forecast6hCount: grapRows.filter((r) => r.stage6h === st.stage).length,
  })),
  stations: grapRows,
}

/* ------------------------------- model health ------------------------------ */

function skillSeries(base: number, amp: number, seed: number): number[] {
  return Array.from({ length: 30 }, (_, i) => {
    const v = base + amp * Math.sin(i / 3.1 + seed) + amp * 0.5 * Math.sin(i / 1.3 + seed * 2)
    return Math.round(v * 1000) / 1000
  })
}

const windowEnds = Array.from({ length: 30 }, (_, i) => new Date(asOfMs - (29 - i) * 24 * HOUR).toISOString().slice(0, 10))

function hourlyFlags(gaps: readonly number[]): boolean[] {
  return Array.from({ length: 24 }, (_, i) => !gaps.includes(i))
}

const minutesAgo = (m: number): string => iso(Date.parse(GENERATED_AT) - m * MINUTE)

function skillOf(
  product: ProductKey,
  vsPersistence: number[] | null,
  vsWindowUpdate: number[] | null,
  n: number | null,
): ModelHealth['skill'][number] {
  const m = PRODUCT_META[product]
  return {
    product,
    label: m.label,
    horizon: m.horizon,
    target: m.target,
    windowEnd: vsPersistence ? windowEnds : [],
    skillVsPersistence: vsPersistence ?? [],
    skillVsWindowUpdate: vsPersistence ? (vsWindowUpdate ?? vsPersistence.map(() => null)) : [],
    currentVsPersistence: vsPersistence ? (vsPersistence[vsPersistence.length - 1] ?? null) : null,
    currentVsWindowUpdate: vsWindowUpdate ? (vsWindowUpdate[vsWindowUpdate.length - 1] ?? null) : null,
    n,
  }
}

const aqi1 = skillSeries(0.5, 0.04, 2.9)
const aqi6 = skillSeries(0.2, 0.05, 0.4)
const aqi6wu = skillSeries(0.11, 0.04, 1.1)
const aqi24 = skillSeries(0.0, 0.05, 1.7)
const aqi24wu = skillSeries(0.15, 0.05, 0.9)
const pm1 = skillSeries(0.08, 0.03, 0.2)
const pm6 = skillSeries(0.21, 0.05, 1.3)

export const modelHealthFixture: ModelHealth = {
  ...meta,
  skill: [
    skillOf('aqi_1h', aqi1, aqi1.map(() => 0), 4236),
    skillOf('aqi_6h', aqi6, aqi6wu, 4506),
    skillOf('aqi_24h', aqi24, aqi24wu, 3971),
    skillOf('pm25_1h', pm1, null, 3758),
    skillOf('pm25_6h', pm6, null, 3354),
  ],
  sourceLag: {
    source: 'openaq',
    newestReadingAt: DATA_AS_OF,
    currentMedianHours: 0.6,
    currentMaxHours: 5.6,
    daily: [
      { day: '2026-10-13', medianHours: 41.5, maxHours: 44, runs: 24 },
      { day: '2026-10-14', medianHours: 12.5, maxHours: 38, runs: 24 },
      { day: '2026-10-15', medianHours: 0.7, maxHours: 5.6, runs: 16 },
    ],
  },
  forecastCoverage: 0.71,
  freshness: [
    { stationId: '3', name: 'Anand Vihar', lastReadingAt: minutesAgo(35), hourly: hourlyFlags([]), note: null },
    { stationId: '4', name: 'Bawana', lastReadingAt: minutesAgo(35), hourly: hourlyFlags([9]), note: '1 hour missing' },
    { stationId: '5', name: 'Dwarka-Sector 8', lastReadingAt: minutesAgo(35), hourly: hourlyFlags([]), note: 'No PM2.5 reading this hour' },
    { stationId: '6', name: 'ITO', lastReadingAt: minutesAgo(35), hourly: hourlyFlags([]), note: 'No weather sensors' },
    { stationId: '7', name: 'Jahangirpuri', lastReadingAt: minutesAgo(335), hourly: hourlyFlags([19, 20, 21, 22, 23]), note: 'no reading for 5 h' },
    { stationId: '8', name: 'Punjabi Bagh', lastReadingAt: minutesAgo(35), hourly: hourlyFlags([]), note: null },
    { stationId: '9', name: 'R K Puram', lastReadingAt: minutesAgo(35), hourly: hourlyFlags([3, 4, 5]), note: '3 hours missing overnight' },
  ],
  jobs: [
    { job: 'ingest', status: 'success', lastRunAt: '2026-10-15T15:10:00+05:30' },
    { job: 'forecast', status: 'success', lastRunAt: '2026-10-15T15:12:00+05:30' },
    { job: 'score', status: 'success', lastRunAt: '2026-10-15T02:10:00+05:30' },
    { job: 'shadow', status: 'partial', lastRunAt: '2026-10-15T15:20:00+05:30' },
  ],
  models: [
    { version: 'aqi-1h-window-update-v1', name: 'Rule-based (24h-window update) 1h AQI', target: 'aqi', horizon: '1h', sha256: 'a'.repeat(64) },
    { version: 'aqi-6h-lgb-live-v1', name: 'LightGBM 6h AQI (live-consistent)', target: 'aqi', horizon: '6h', sha256: 'b'.repeat(64) },
    { version: 'aqi-24h-hybrid-live-v1', name: '50/50 persistence + Ridge 24h AQI (live-consistent, low skill)', target: 'aqi', horizon: '24h', sha256: 'c'.repeat(64) },
    { version: 'pm25-1h-hgb-live-v1', name: 'HistGradientBoosting 1h PM2.5 (live-consistent)', target: 'pm25', horizon: '1h', sha256: 'd'.repeat(64) },
    { version: 'pm25-6h-hgb-live-v1', name: 'HistGradientBoosting 6h PM2.5 (live-consistent)', target: 'pm25', horizon: '6h', sha256: 'e'.repeat(64) },
  ],
}

/* -------------------------------- backtest --------------------------------- */

const TEST = 'test 2025-11-01..2025-12-31'
const REPLAY = 'replay 2026-09-01..2026-10-07'

function evidence(
  product: ProductKey,
  window: string,
  n: number,
  p: [number, number, number],
  w: [number, number, number] | null,
): Backtest['evidence'][number] {
  return {
    product,
    label: PRODUCT_META[product].label,
    window,
    n,
    skillVsPersistence: p[0],
    skillVsPersistenceLo: p[1],
    skillVsPersistenceHi: p[2],
    skillVsWindowUpdate: w ? w[0] : null,
    skillVsWindowUpdateLo: w ? w[1] : null,
    skillVsWindowUpdateHi: w ? w[2] : null,
  }
}

export const backtestFixture: Backtest = {
  note: 'Skill = 1 - MAE_model / MAE_reference with 95% day-block bootstrap intervals, from the files in reports/.',
  evidence: [
    evidence('aqi_1h', TEST, 10221, [0.553, 0.51, 0.591], null),
    evidence('aqi_6h', TEST, 10181, [0.309, 0.252, 0.355], [0.304, 0.243, 0.357]),
    evidence('aqi_24h', TEST, 10044, [0.097, 0.063, 0.128], null),
    evidence('pm25_1h', TEST, 9970, [0.202, 0.183, 0.219], null),
    evidence('pm25_6h', TEST, 9862, [0.364, 0.316, 0.407], null),
    evidence('aqi_1h', REPLAY, 4236, [0.514, 0.46, 0.564], null),
    evidence('aqi_6h', REPLAY, 4506, [0.206, 0.124, 0.285], [0.119, 0.048, 0.179]),
    evidence('aqi_24h', REPLAY, 3971, [-0.014, -0.104, 0.058], null),
    evidence('pm25_1h', REPLAY, 3758, [0.084, 0.053, 0.11], null),
    evidence('pm25_6h', REPLAY, 3354, [0.208, 0.14, 0.27], null),
  ],
}

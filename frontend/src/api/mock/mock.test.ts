import { categoryOf } from '@/lib/aqi'
import { findForecast, rankByNow } from '@/lib/forecast'
import { ApiError } from '../http'
import { createMockClient } from './client'
import { DROPPED_PM25_REASON, NO_RULE_REASON, overviewFixture, stationsFixture, STALE_REASON } from './data'

const client = createMockClient()

describe('mock client serves schema-valid data', () => {
  it('answers every endpoint', async () => {
    await expect(client.health()).resolves.toMatchObject({ status: 'ok' })
    await expect(client.overview()).resolves.toHaveProperty('network')
    await expect(client.stations()).resolves.toHaveProperty('stations')
    await expect(client.grapAlerts()).resolves.toHaveProperty('disclaimer')
    await expect(client.modelHealth()).resolves.toHaveProperty('sourceLag')
    await expect(client.backtest()).resolves.toHaveProperty('evidence')
  })

  it('answers every station for both targets', async () => {
    for (const { id } of stationsFixture.stations) {
      for (const target of ['aqi', 'pm25'] as const) {
        const forecast = await client.stationForecast(id, target)
        expect(forecast.target).toBe(target)
        expect(forecast.forecasts).toHaveLength(3)
      }
    }
  })

  it('rejects an unknown station with a 404 ApiError', async () => {
    const error = await client.stationForecast('atlantis', 'aqi').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
  })
})

describe('the sample shows the states the real API produces', () => {
  const byName = (name: string) => overviewFixture.stations.find((s) => s.name === name)

  it('never ships a 24h PM2.5 forecast: it is withheld with the policy reason', async () => {
    const { forecasts } = await client.stationForecast('3', 'pm25')
    const day = forecasts.find((f) => f.horizon === '24h')
    expect(day).toMatchObject({ status: 'withheld', value: null })
    expect(day?.reason).toMatch(/No 24h PM2.5 forecast is published/)
  })

  it('has a station with a stale feed: every product unavailable, with the job’s reason, and no numbers', () => {
    const stale = byName('Jahangirpuri')
    expect(stale?.now?.stale).toBe(true)
    const products = stale?.forecasts.filter((f) => f.product !== 'pm25_24h') ?? []
    expect(products.length).toBeGreaterThan(0)
    for (const f of products) {
      expect(f).toMatchObject({ status: 'unavailable', value: null, persistence: null, reason: STALE_REASON })
    }
  })

  it('has a station whose PM2.5 products were dropped but whose AQI forecasts exist', () => {
    const dropped = byName('Dwarka-Sector 8')
    expect(findForecast(dropped?.forecasts ?? [], 'pm25_6h')).toMatchObject({ status: 'unavailable', reason: DROPPED_PM25_REASON })
    expect(findForecast(dropped?.forecasts ?? [], 'aqi_6h')?.status).toBe('ok')
  })

  it('has a station where only the 1h rule is unavailable', () => {
    const ito = byName('ITO')
    expect(findForecast(ito?.forecasts ?? [], 'aqi_1h')).toMatchObject({ status: 'unavailable', reason: NO_RULE_REASON })
    expect(findForecast(ito?.forecasts ?? [], 'aqi_6h')?.status).toBe('ok')
  })

  it('labels the products as the ADR says', () => {
    const forecasts = byName('Bawana')?.forecasts ?? []
    expect(findForecast(forecasts, 'aqi_1h')).toMatchObject({ kind: 'rule', label: 'Rule-based (24h-window update)', experimental: false })
    expect(findForecast(forecasts, 'aqi_24h')).toMatchObject({ experimental: true })
    expect(findForecast(forecasts, 'aqi_24h')?.label).toMatch(/about as accurate as assuming no change/)
    expect(findForecast(forecasts, 'pm25_6h')).toMatchObject({ kind: 'model', experimental: false })
  })

  it('carries plain persistence on every ok forecast, and a window-update reference on AQI only', () => {
    for (const station of overviewFixture.stations) {
      for (const f of station.forecasts.filter((x) => x.status === 'ok')) {
        expect(f.persistence).not.toBeNull()
        expect(f.windowUpdate === null).toBe(f.target === 'pm25')
      }
    }
  })

  it('persistence is the station’s current AQI for every ok AQI forecast', () => {
    for (const station of overviewFixture.stations) {
      for (const f of station.forecasts.filter((x) => x.status === 'ok' && x.target === 'aqi')) {
        expect(f.persistence).toBe(station.now?.value)
      }
    }
  })
})

describe('fixtures agree with each other', () => {
  it('computes the network summary from the stations with a fresh reading', () => {
    const fresh = overviewFixture.stations.filter((s) => s.now && !s.now.stale)
    const mean = fresh.reduce((sum, s) => sum + (s.now?.value ?? 0), 0) / fresh.length
    expect(overviewFixture.network.stationsWithData).toBe(fresh.length)
    expect(overviewFixture.network.meanAqiNow).toBeCloseTo(mean, 1)
    expect(overviewFixture.network.categoryNow).toBe(categoryOf(mean).label)
  })

  it('counts stations with a forecast the way the API does', () => {
    const withForecast = overviewFixture.stations.filter((s) => s.forecasts.some((f) => f.status === 'ok'))
    expect(overviewFixture.network.stationsForecast).toBe(withForecast.length)
  })

  it('ranks the stale station last-but-for-readings, not first', () => {
    expect(rankByNow(overviewFixture.stations)[0]?.name).toBe('Bawana')
  })

  it('has GRAP stage counts that match the station values', async () => {
    const { stages, stations } = await client.grapAlerts()
    for (const stage of stages) {
      expect(stage.nowCount).toBe(stations.filter((s) => s.stageNow === stage.stage).length)
      expect(stage.forecast6hCount).toBe(stations.filter((s) => s.stage6h === stage.stage).length)
    }
  })

  it('gives the stale station no GRAP value rather than its old one', async () => {
    const { stations } = await client.grapAlerts()
    expect(stations.find((s) => s.name === 'Jahangirpuri')).toMatchObject({ now: null, stageNow: null, forecast6h: null, forecast24h: null })
  })

  it('has evidence for every published product in the test window and none for PM2.5 24h', async () => {
    const { evidence } = await client.backtest()
    const test = evidence.filter((e) => e.window.startsWith('test')).map((e) => e.product)
    expect(test.sort()).toEqual(['aqi_1h', 'aqi_24h', 'aqi_6h', 'pm25_1h', 'pm25_6h'])
    expect(evidence.some((e) => e.product === 'pm25_24h')).toBe(false)
  })
})

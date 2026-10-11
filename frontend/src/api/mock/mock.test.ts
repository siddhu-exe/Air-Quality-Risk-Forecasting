import { categoryOf } from '@/lib/aqi'
import { ApiError } from '../http'
import { createMockClient } from './client'
import { overviewFixture, stationsFixture } from './data'

const client = createMockClient()

describe('mock client serves schema-valid data', () => {
  it('answers every endpoint', async () => {
    await expect(client.health()).resolves.toMatchObject({ status: 'ok' })
    await expect(client.overview()).resolves.toMatchObject({ grapStageInForce: 'II' })
    await expect(client.stations()).resolves.toHaveProperty('stations')
    await expect(client.grapAlerts()).resolves.toHaveProperty('alerts')
    await expect(client.modelHealth()).resolves.toHaveProperty('skill')
    await expect(client.backtest()).resolves.toHaveProperty('alertRules')
  })

  it('answers every station for both targets', async () => {
    for (const { id } of stationsFixture.stations) {
      for (const target of ['aqi', 'pm25'] as const) {
        const forecast = await client.stationForecast(id, target)
        expect(forecast.target).toBe(target)
        expect(forecast.history).toHaveLength(73)
        expect(forecast.forecast).toHaveLength(target === 'aqi' ? 25 : 7)
      }
    }
  })

  it('rejects an unknown station with a 404 ApiError', async () => {
    const error = await client.stationForecast('atlantis', 'aqi').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
  })

  it('never ships a 24h PM2.5 forecast, but still reports its backtest skill', async () => {
    const { horizons } = await client.stationForecast('anand-vihar', 'pm25')
    const h24 = horizons.find((h) => h.horizon === '24h')
    expect(h24?.value).toBeNull()
    expect(h24?.backtestSkill).toBeLessThan(0)
  })

  it('withholds weather only for the station without sensors', async () => {
    expect((await client.stationForecast('ito', 'aqi')).weather).toBeNull()
    expect((await client.stationForecast('bawana', 'aqi')).weather).not.toBeNull()
  })
})

describe('fixtures agree with each other', () => {
  it('keeps every station inside its own 80% range', () => {
    for (const s of overviewFixture.stations) {
      expect(s.lo).toBeLessThanOrEqual(s.forecast24h)
      expect(s.forecast24h).toBeLessThanOrEqual(s.hi)
    }
  })

  it('has GRAP stage counts that match the station forecasts', async () => {
    const { stages } = await client.grapAlerts()
    for (const stage of stages) {
      const inStage = (aqi: number) => {
        const v = Math.round(aqi)
        return v >= stage.min && (stage.max === null || v <= stage.max)
      }
      expect(stage.nowCount).toBe(overviewFixture.stations.filter((s) => inStage(s.now)).length)
      expect(stage.tomorrowCount).toBe(overviewFixture.stations.filter((s) => inStage(s.forecast24h)).length)
    }
  })

  it('lists alert stations that exist and clear the alert probability', async () => {
    const { alerts, alertMinProbability } = await client.grapAlerts()
    for (const a of alerts) {
      expect(overviewFixture.stations.some((s) => s.id === a.stationId)).toBe(true)
      expect(a.pSevere).toBeGreaterThanOrEqual(alertMinProbability)
    }
  })

  it('shows the city average the design shows', () => {
    expect(categoryOf(overviewFixture.network.forecast24h).label).toBe('Very Poor')
    expect(overviewFixture.network.forecast24h - overviewFixture.network.now).toBe(18)
  })
})

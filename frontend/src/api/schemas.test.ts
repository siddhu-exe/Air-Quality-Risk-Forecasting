import { makeForecast } from './mock/data'
import { ForecastSchema } from './schemas'

const past = {
  issuedAt: '2026-10-07T19:00:00+05:30',
  validAt: '2026-10-08T01:00:00+05:30',
  value: 212.4,
  category: 'Poor',
  persistence: 205,
  windowUpdate: 200,
  modelVersion: 'aqi-6h-lgb-live-v1',
}

describe('ForecastSchema lastIssued', () => {
  it('accepts the last issued forecast on an unavailable one, and treats an absent field as null', () => {
    const unavailable = makeForecast('aqi_6h', 'unavailable', { reason: 'the forecast job has not run recently' })
    const { lastIssued: _omitted, ...withoutField } = unavailable
    expect(ForecastSchema.parse(withoutField).lastIssued).toBeNull() // an older API response
    expect(ForecastSchema.parse({ ...unavailable, lastIssued: past }).lastIssued).toMatchObject({ value: 212.4 })
  })

  it('rejects a current forecast that also carries a last-issued block, so history cannot pose as a forecast for now', () => {
    const ok = makeForecast('aqi_6h', 'ok', { value: 150 })
    expect(ForecastSchema.safeParse({ ...ok, lastIssued: past }).success).toBe(false)
  })

  it('still demands that an unavailable forecast carries no number of its own', () => {
    const unavailable = makeForecast('aqi_6h', 'unavailable', { reason: 'x' })
    expect(ForecastSchema.safeParse({ ...unavailable, value: 212.4, lastIssued: past }).success).toBe(false)
  })
})

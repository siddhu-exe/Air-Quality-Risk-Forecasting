import { render, screen, within } from '@testing-library/react'
import { makeForecast, overviewFixture } from '@/api/mock/data'
import type { Overview, PastForecast } from '@/api/schemas'
import { newestIssue } from '@/lib/forecast'
import { LastIssuedPanel } from './LastIssuedPanel'

const PAST: PastForecast = {
  issuedAt: '2026-10-07T19:00:00+05:30',
  validAt: '2026-10-08T01:00:00+05:30',
  value: 212.4,
  category: 'Poor',
  persistence: 205,
  windowUpdate: 200,
  modelVersion: 'aqi-6h-lgb-live-v1',
}

/** The network is stale and the forecast job stopped: every product is unavailable; some carry the last issued value. */
function stopped(withHistory: boolean): Overview {
  const clone: Overview = structuredClone(overviewFixture)
  clone.stale = true
  clone.stations = clone.stations.map((s, i) => ({
    ...s,
    forecasts: s.forecasts.map((f) =>
      f.product === 'pm25_24h'
        ? f
        : makeForecast(f.product, 'unavailable', {
            reason: 'the forecast job has not run recently',
            lastIssued: withHistory && i === 0 && f.product === 'aqi_6h' ? PAST : null,
          }),
    ),
  }))
  return clone
}

describe('LastIssuedPanel', () => {
  it('labels the last issued forecast as past, with the time it was issued and the time it predicted', () => {
    const overview = stopped(true)
    render(<LastIssuedPanel stations={overview.stations} />)
    expect(screen.getByRole('heading', { name: 'Last forecast issued' })).toBeInTheDocument()
    expect(screen.getByText('Past · not a forecast for now')).toBeInTheDocument()
    expect(screen.getByText(/Issued 19:00 IST on Wed 7 Oct\./)).toBeInTheDocument()
    expect(screen.getByText(/say nothing about the air now/)).toBeInTheDocument()
    const row = screen.getByRole('row', { name: new RegExp(overview.stations[0]!.name) })
    expect(within(row).getByText('212')).toBeInTheDocument()
    expect(within(row).getByText('for Thu 8 Oct 01:00')).toBeInTheDocument()
  })

  it('says plainly that nothing was ever issued, and shows no number', () => {
    render(<LastIssuedPanel stations={stopped(false).stations} />)
    expect(screen.getByText('No forecast has been issued yet.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('finds the newest issue time across stations', () => {
    expect(newestIssue(stopped(false).stations)).toBeNull()
    expect(newestIssue(stopped(true).stations)).toBe(PAST.issuedAt)
  })
})

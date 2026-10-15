import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { overviewFixture } from '@/api/mock/data'
import type { Overview } from '@/api/schemas'
import { AdvicePanel } from './overview/AdvicePanel'
import { CityHero } from './overview/CityHero'
import { StationList, StationTable } from './overview/StationTable'

/** What the overview shows when the data is bad: no readings, no forecasts, everything stale. */

function noData(): Overview {
  const clone: Overview = structuredClone(overviewFixture)
  clone.network = { stationsWithData: 0, stationsTotal: 7, meanAqiNow: null, categoryNow: null, stationsForecast: 0 }
  clone.stale = true
  clone.issuedAt = null
  clone.stations = clone.stations.map((s) => ({
    ...s,
    now: null,
    forecasts: s.forecasts.map((f) => ({
      ...f,
      status: f.product === 'pm25_24h' ? 'withheld' : 'unavailable',
      reason: f.product === 'pm25_24h' ? f.reason : 'the forecast job has not run recently (no forecast has been issued yet)',
      value: null,
      persistence: null,
      windowUpdate: null,
      category: null,
      validAt: null,
      issuedAt: null,
      modelVersion: null,
    })),
  }))
  return clone
}

describe('overview with no data at all', () => {
  it('shows a dash and says there is no current AQI, never a number', () => {
    render(<CityHero overview={noData()} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('No current AQI')
    expect(screen.getByRole('heading', { level: 1 })).not.toHaveTextContent(/\d/)
    expect(screen.getByText(/No station has a recent reading/)).toBeInTheDocument()
    expect(screen.getAllByText('no station has one')).toHaveLength(2)
    expect(screen.queryByRole('img', { name: /on the CPCB scale/ })).not.toBeInTheDocument()
  })

  it('gives advice only from a real reading', () => {
    render(
      <MemoryRouter>
        <AdvicePanel aqiNow={null} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'No current reading.' })).toBeInTheDocument()
    expect(screen.getByText(/no current AQI to base advice on/)).toBeInTheDocument()
  })

  it('lists every station with the reason in every forecast cell', () => {
    render(
      <MemoryRouter>
        <StationTable stations={noData().stations} />
        <StationList stations={noData().stations} />
      </MemoryRouter>,
    )
    const table = screen.getAllByRole('region', { name: 'Forecast by station' })[0] as HTMLElement
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(7)
    for (const row of rows) {
      expect(within(row).getAllByText(/Forecast job not running/)).toHaveLength(5)
      expect(within(row).getByText(/no reading/)).toBeInTheDocument()
      expect(row.textContent).not.toMatch(/\d{3}/)
    }
  })
})

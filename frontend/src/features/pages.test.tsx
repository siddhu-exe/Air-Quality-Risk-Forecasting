import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAt } from '@/test/renderApp'

/** The pages against the sample API: what a person would see and do. */

describe('Overview', () => {
  it('shows tomorrow\'s city forecast, its range and the advice', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { level: 1, name: /Forecast AQI 374/ })).toBeInTheDocument()
    expect(screen.getAllByText('Very Poor').length).toBeGreaterThan(0)
    expect(screen.getByText(/Likely between/)).toHaveTextContent('Likely between 325 and 431 (80% range)')
    expect(screen.getByRole('heading', { name: 'Keep outdoor effort short.' })).toBeInTheDocument()
    expect(screen.getByText(/GRAP Stage II restrictions in force/)).toBeInTheDocument()
  })

  it('links each station to its page, worst first', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    // jsdom has no CSS, so the desktop table and the phone list are both present; the table comes first.
    const table = screen.getAllByRole('region', { name: 'Tomorrow by station' })[0] as HTMLElement
    const links = within(table).getAllByRole('link')
    expect(links).toHaveLength(7)
    expect(links[0]).toHaveAccessibleName(/^Bawana: AQI 401 now, 418 tomorrow, Severe, 63% chance of Severe/)
    expect(links[0]).toHaveAttribute('href', '/stations/bawana')
  })

  it('describes the map for assistive tech', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.getByRole('group', { name: /Map of Delhi with 7 monitoring stations: 1 Severe, 6 Very Poor/ })).toBeInTheDocument()
  })

  it('states the backtest figures from the API', async () => {
    renderAt('/')
    expect(await screen.findByText('~11%')).toBeInTheDocument()
    expect(screen.getByText('76%')).toBeInTheDocument()
    expect(screen.getByText(/in two past winters/)).toBeInTheDocument()
  })
})

describe('Stations', () => {
  it('sends /stations to the worst station', async () => {
    const router = renderAt('/stations')
    expect(await screen.findByRole('heading', { level: 1, name: 'Bawana' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/stations/bawana')
  })

  it('marks the chosen station and switches by link', async () => {
    const user = userEvent.setup()
    const router = renderAt('/stations/anand-vihar')
    const pills = await screen.findByRole('navigation', { name: 'Choose a station' })
    expect(within(pills).getByRole('link', { name: 'Anand Vihar' })).toHaveAttribute('aria-current', 'true')

    await user.click(within(pills).getByRole('link', { name: 'R K Puram' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'R K Puram' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/stations/r-k-puram')
  })

  it('shows all three horizons for AQI with the 24h range', async () => {
    renderAt('/stations/anand-vihar')
    const horizons = await screen.findByRole('region', { name: 'Forecast by horizon' })
    expect(within(horizons).getByText('412')).toBeInTheDocument()
    expect(within(horizons).getByText(/likely 360–470/)).toBeInTheDocument()
    expect(within(horizons).getByText('14:00 tomorrow')).toBeInTheDocument()
  })

  it('withholds the 24h PM2.5 forecast and says why', async () => {
    const user = userEvent.setup()
    renderAt('/stations/anand-vihar')
    await screen.findByRole('region', { name: 'Forecast by horizon' })
    await user.click(screen.getByRole('button', { name: 'PM2.5' }))

    expect(await screen.findByText(/Not shown: in backtests this model did not beat/)).toBeInTheDocument()
    const horizons = screen.getByRole('region', { name: 'Forecast by horizon' })
    expect(within(horizons).queryByText('412')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /next 6 hours \(PM2\.5/ })).toBeInTheDocument()
  })

  it('explains a station without weather sensors', async () => {
    renderAt('/stations/ito')
    expect(await screen.findByText(/This station has no weather sensors/)).toBeInTheDocument()
  })

  it('tells the reader when the station does not exist', async () => {
    renderAt('/stations/atlantis')
    expect(await screen.findByRole('heading', { name: 'Station not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to Bawana/ })).toBeInTheDocument()
  })
})

describe('Operations', () => {
  it('marks the stage in force and counts stations per stage', async () => {
    renderAt('/operations')
    await screen.findByRole('heading', { level: 1, name: 'GRAP outlook' })
    const stages = screen.getByRole('region', { name: 'GRAP stages' })
    expect(within(stages).getAllByText('In force')).toHaveLength(1)
    expect(screen.getByText(/Stage II is in force\. Two stations are forecast to reach Severe/)).toBeInTheDocument()
  })

  it('lists the stations at risk of Severe with their status', async () => {
    renderAt('/operations')
    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(5) // header + 4 alerts
    expect(within(rows[1] as HTMLElement).getByText('Bawana')).toBeInTheDocument()
    expect(within(rows[1] as HTMLElement).getByText('Active')).toBeInTheDocument()
    expect(within(rows[2] as HTMLElement).getByText('New')).toBeInTheDocument()
  })

  it('switches the alert rule and never rounds 99.8% up to 100%', async () => {
    const user = userEvent.setup()
    renderAt('/operations')
    expect(await screen.findByText('61%')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cost-aware · 275' }))
    expect(await screen.findByText('99.8%')).toBeInTheDocument()
    const rates = screen.getByText('False alarm rate').closest('div') as HTMLElement
    expect(within(rates).getByText('93%')).toBeInTheDocument()
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
  })

  it('reports lead times honestly where copy-last catches more', async () => {
    renderAt('/operations')
    expect(await screen.findByText(/Copy-last catches more episodes here/)).toBeInTheDocument()
  })
})

describe('Model health', () => {
  it('shows each model\'s status against copy-last', async () => {
    renderAt('/model-health')
    await screen.findByRole('heading', { level: 1, name: 'Model health' })
    expect(screen.getAllByText('Beating copy-last')).toHaveLength(2)
    expect(screen.getByText('About even')).toBeInTheDocument()
    expect(screen.getByText('+0.09')).toBeInTheDocument()
  })

  it('reports Brier scores with the backtest verdict', async () => {
    renderAt('/model-health')
    expect(await screen.findByText(/Backtest: 0\.194 vs 0\.196, a tie\./)).toBeInTheDocument()
  })

  it('measures data age on the server clock and flags a late feed', async () => {
    renderAt('/model-health')
    const table = await screen.findByRole('table')
    const jahangirpuri = within(table).getByRole('row', { name: /Jahangirpuri/ })
    expect(within(jahangirpuri).getByText('2 h 14 min')).toBeInTheDocument()
    expect(within(jahangirpuri).getByText('(late)')).toBeInTheDocument()
    const anand = within(table).getByRole('row', { name: /Anand Vihar/ })
    expect(within(anand).getByText('14 min')).toBeInTheDocument()
    expect(within(anand).getByRole('img', { name: '24 of 24 hourly readings received' })).toBeInTheDocument()
  })

  it('lists jobs with their status in words', async () => {
    renderAt('/model-health')
    expect(await screen.findByText('Retry · 12:00')).toBeInTheDocument()
    expect(screen.getByText('OK · 14:10')).toBeInTheDocument()
  })
})

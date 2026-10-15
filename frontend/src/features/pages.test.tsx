import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAt } from '@/test/renderApp'

/** The pages against the sample API: what a person would see and do. */

describe('Overview', () => {
  it('shows the city average right now, its category and the forecasts that exist', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { level: 1, name: /City average AQI now 288/ })).toBeInTheDocument()
    expect(screen.getAllByText('Poor').length).toBeGreaterThan(0)
    expect(screen.getByText('6 of 7 stations reporting')).toBeInTheDocument()
    expect(screen.getByText('In 1 hour · rule-based').parentElement).toHaveTextContent('296')
    expect(screen.getByText('In 6 hours · model').parentElement).toHaveTextContent('294')
    expect(screen.getByText('In 6 hours · model').parentElement).toHaveTextContent('6 of 7 stations')
    expect(screen.getByRole('heading', { name: 'Cut back on long outdoor effort.' })).toBeInTheDocument()
  })

  it('lists every station worst first and links each to its page', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    // jsdom has no CSS, so the desktop table and the phone list are both present; the table comes first.
    const table = screen.getAllByRole('region', { name: 'Forecast by station' })[0] as HTMLElement
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(7)
    const first = within(rows[0] as HTMLElement).getByRole('link')
    expect(first).toHaveAccessibleName('Bawana: AQI 331 now, 338 in 6 hours')
    expect(first).toHaveAttribute('href', '/stations/4')
  })

  it('never leaves a forecast cell blank or fakes a number: it gives the reason', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    const table = screen.getAllByRole('region', { name: 'Forecast by station' })[0] as HTMLElement

    const stale = within(table).getByRole('row', { name: /Jahangirpuri/ })
    expect(within(stale).getAllByText(/Stale data/)).toHaveLength(5)
    expect(within(stale).getAllByText(/stale: newest reading is 4\.6 h older/).length).toBeGreaterThan(0) // full reason for screen readers
    expect(within(stale).getByText(/old reading/)).toBeInTheDocument()

    const dropped = within(table).getByRole('row', { name: /Dwarka-Sector 8/ })
    expect(within(dropped).getAllByText(/No current reading/)).toHaveLength(2) // PM2.5 +1h and +6h
    expect(within(dropped).getByText('277')).toBeInTheDocument() // its AQI +1h still shows

    const noRule = within(table).getByRole('row', { name: /ITO/ })
    expect(within(noRule).getByText(/No hourly AQI/)).toBeInTheDocument()
  })

  it('labels the rule, the model and the experimental 24h forecast, which shows plain persistence beside it', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    const table = screen.getAllByRole('region', { name: 'Forecast by station' })[0] as HTMLElement
    expect(within(table).getByRole('columnheader', { name: /AQI \+1h\s*rule-based/ })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: /AQI \+24h\s*experimental/ })).toBeInTheDocument()
    const bawana = within(table).getByRole('row', { name: /Bawana/ })
    expect(within(bawana).getByText('345')).toBeInTheDocument()
    expect(within(bawana).getByText('same as now: 331')).toBeInTheDocument()
  })

  it('describes the map for assistive tech, including a station with an old reading', async () => {
    renderAt('/')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.getByRole('group', { name: /Map of Delhi with 7 monitoring stations: 3 Very Poor, 4 Poor/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Jahangirpuri: AQI 301 now, Very Poor, reading is old' })).toBeInTheDocument()
  })

  it('states the backtest figures from the API, including the replay that was no better than no change', async () => {
    renderAt('/')
    expect(await screen.findByText('55%')).toBeInTheDocument()
    expect(screen.getByText('31%')).toBeInTheDocument()
    expect(screen.getByText(/in the Sep–Oct 2026 replay it was −1%, about the same as assuming no change/)).toBeInTheDocument()
  })
})

describe('Stations', () => {
  it('sends /stations to the worst station', async () => {
    const router = renderAt('/stations')
    expect(await screen.findByRole('heading', { level: 1, name: 'Bawana' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/stations/4')
  })

  it('marks the chosen station and switches by link', async () => {
    const user = userEvent.setup()
    const router = renderAt('/stations/3')
    const pills = await screen.findByRole('navigation', { name: 'Choose a station' })
    expect(within(pills).getByRole('link', { name: 'Anand Vihar' })).toHaveAttribute('aria-current', 'true')

    await user.click(within(pills).getByRole('link', { name: 'R K Puram' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'R K Puram' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/stations/9')
  })

  it('shows the three AQI products with their labels, values and plain persistence', async () => {
    renderAt('/stations/3')
    const cards = await screen.findByRole('region', { name: 'Forecast by horizon' })
    expect(within(cards).getByText('Rule-based: updates the 24-hour average')).toBeInTheDocument()
    expect(within(cards).getByText('Experimental: about as accurate as assuming no change')).toBeInTheDocument()
    expect(within(cards).getByText('325')).toBeInTheDocument() // 6h
    expect(within(cards).getAllByText('Same as now')).toHaveLength(3)
    expect(within(cards).getAllByText('318')).toHaveLength(3) // persistence on each card
    expect(within(cards).getAllByText('24h-window update')).toHaveLength(2) // reference on 6h and 24h, not on the rule itself
    expect(within(cards).getByText('+55% MAE')).toBeInTheDocument()
  })

  it('withholds the 24h PM2.5 forecast and says why', async () => {
    const user = userEvent.setup()
    renderAt('/stations/3')
    await screen.findByRole('region', { name: 'Forecast by horizon' })
    await user.click(screen.getByRole('button', { name: 'PM2.5' }))

    const cards = await screen.findByRole('region', { name: 'Forecast by horizon' })
    expect(await within(cards).findByText(/No 24h PM2.5 forecast is published/)).toBeInTheDocument()
    expect(within(cards).getByText('Not published')).toBeInTheDocument()
    expect(within(cards).getByText('158')).toBeInTheDocument() // PM2.5 +1h
  })

  it('explains each missing forecast at a station with a stale feed, and draws no chart', async () => {
    renderAt('/stations/7')
    expect(await screen.findByRole('heading', { level: 1, name: 'Jahangirpuri' })).toBeInTheDocument()
    expect(await screen.findByText(/Last reading .* too old to forecast from/)).toBeInTheDocument()
    expect(await screen.findByText(/no recent AQI readings for this station/)).toBeInTheDocument()
    const cards = await screen.findByRole('region', { name: 'Forecast by horizon' })
    expect(within(cards).getAllByText(/stale: newest reading is 4\.6 h older/)).toHaveLength(3)
    expect(screen.queryByRole('img', { name: /Jahangirpuri: AQI over the past 72 hours/ })).not.toBeInTheDocument()
  })

  it('shows the AQI chart without a 1h forecast when only the rule is missing', async () => {
    renderAt('/stations/6')
    const cards = await screen.findByRole('region', { name: 'Forecast by horizon' })
    expect(within(cards).getByText(/no valid current hourly AQI/)).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: /ITO: AQI over the past 72 hours .*forecast 259 at \+24h/ })).toBeInTheDocument()
  })

  it('explains a station without weather sensors', async () => {
    renderAt('/stations/6')
    expect(await screen.findByText(/No weather readings for this station right now/)).toBeInTheDocument()
  })

  it('tells the reader when the station does not exist', async () => {
    renderAt('/stations/atlantis')
    expect(await screen.findByRole('heading', { name: 'Station not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to Bawana/ })).toBeInTheDocument()
  })
})

describe('Operations', () => {
  it('says what the stages are based on and that it is not an advisory', async () => {
    renderAt('/operations')
    await screen.findByRole('heading', { level: 1, name: 'GRAP outlook' })
    expect(screen.getByText(/Indicative only, not an official advisory/)).toBeInTheDocument()
    const stages = screen.getByRole('region', { name: 'GRAP stages' })
    expect(within(stages).getAllByText('Indicated now')).toHaveLength(1)
    expect(screen.getByText(/The city mean of 288 indicates Stage I\. No station is forecast to reach Severe within six hours/)).toBeInTheDocument()
  })

  it('lists each station now, in six hours and in 24 hours with its persistence, and says when there is no value', async () => {
    renderAt('/operations')
    const region = await screen.findByRole('region', { name: 'Stations against the stage bands' })
    const rows = within(region).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(7)
    const bawana = within(rows[0] as HTMLElement)
    expect(bawana.getByText('Bawana')).toBeInTheDocument()
    expect(bawana.getByText('same as now: 331')).toBeInTheDocument()
    const stale = within(within(region).getByRole('row', { name: /Jahangirpuri/ }))
    expect(stale.getAllByText(/no value|no forecast/).length).toBe(3)
  })

  it('shows the evidence table with intervals for both windows', async () => {
    renderAt('/operations')
    const region = await screen.findByRole('region', { name: 'How good are these forecasts?' })
    expect(within(region).getAllByRole('row')).toHaveLength(1 + 10)
    const rule = within(region).getAllByRole('row', { name: /AQI \+1h · rule-based/ })[0] as HTMLElement
    expect(rule).toHaveTextContent('+0.55 [+0.51, +0.59]')
    const replay = within(region).getByRole('row', { name: /AQI \+24h · experimental replay/ })
    expect(replay).toHaveTextContent('−0.01 [−0.10, +0.06]')
  })
})

describe('Model health', () => {
  it('shows a card per published product with skill against both references', async () => {
    renderAt('/model-health')
    await screen.findByRole('heading', { level: 1, name: 'Model health' })
    const cards = screen.getByRole('region', { name: 'Rolling 30-day skill' })
    expect(within(cards).getAllByRole('heading', { level: 2 })).toHaveLength(5)
    expect(within(cards).getAllByText('vs same-as-now')).toHaveLength(5)
    expect(within(cards).getAllByText('vs 24h-window update')).toHaveLength(2) // AQI 6h and 24h; the 1h rule is the reference itself
    expect(within(cards).getByText(/A rule, not a model/)).toBeInTheDocument()
  })

  it('reports the source lag now and by day, and the share of stations with a forecast', async () => {
    renderAt('/model-health')
    const lag = await screen.findByRole('region', { name: 'Data source' })
    expect(within(lag).getByText('Source lag · openaq')).toBeInTheDocument()
    expect(within(lag).getByText('36 min')).toBeInTheDocument()
    expect(within(lag).getByText('71%')).toBeInTheDocument()
    const table = within(lag).getByRole('table')
    expect(within(within(table).getByRole('row', { name: /2026-10-13/ })).getByText('41.5 h')).toBeInTheDocument()
  })

  it('measures data age on the server clock and flags a late feed', async () => {
    renderAt('/model-health')
    const table = await screen.findByRole('table', { name: /Last reading/ }).catch(() => screen.getAllByRole('table')[1] as HTMLElement)
    const jahangirpuri = within(table).getByRole('row', { name: /Jahangirpuri/ })
    expect(within(jahangirpuri).getByText('5 h 35 min')).toBeInTheDocument()
    expect(within(jahangirpuri).getByText('(late)')).toBeInTheDocument()
    const anand = within(table).getByRole('row', { name: /Anand Vihar/ })
    expect(within(anand).getByText('35 min')).toBeInTheDocument()
    expect(within(anand).getByRole('img', { name: '24 of 24 hourly readings received' })).toBeInTheDocument()
  })

  it('lists jobs with their status in words, and that the WAQI shadow job is never used for forecasts', async () => {
    renderAt('/model-health')
    expect(await screen.findByText(/Partial · 15:20/)).toBeInTheDocument()
    expect(screen.getAllByText(/OK · /).length).toBeGreaterThan(0)
    expect(screen.getByText(/never used for forecasts/)).toBeInTheDocument()
  })
})

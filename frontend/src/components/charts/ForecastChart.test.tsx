import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CHART } from '@/lib/chart'
import { ForecastChart } from './ForecastChart'

const NOW = Date.parse('2026-10-11T14:00:00+05:30')
const at = (h: number): string => new Date(NOW + h * 3_600_000).toISOString()

const history = Array.from({ length: 73 }, (_, i) => ({ t: at(i - 72), value: 300 + i }))
const forecast = Array.from({ length: 7 }, (_, j) => ({ t: at(j), median: 372 + j * 5, lo: 360 + j * 3, hi: 384 + j * 8 }))

function renderChart(target: 'aqi' | 'pm25' = 'aqi') {
  render(<ForecastChart subject="Bawana" target={target} history={history} forecast={forecast} />)
}

/** jsdom has no layout: give the plot surface a 960 px width so 1 px is 1 chart unit. */
function surfaceOf(): HTMLElement {
  const surface = screen.getByRole('img').parentElement
  if (!surface) throw new Error('no chart surface')
  surface.getBoundingClientRect = () => ({ left: 0, width: CHART.width, top: 0, height: CHART.height, right: CHART.width, bottom: CHART.height, x: 0, y: 0, toJSON: () => ({}) })
  return surface
}

describe('ForecastChart', () => {
  it('describes the series in words for screen readers', () => {
    renderChart()
    expect(screen.getByRole('img')).toHaveAccessibleName(/Bawana: AQI over the past 72 hours rising to 372, forecast 402 at \+6h/)
  })

  it('shows a readout for the hour under the pointer, and hides it when the pointer leaves', () => {
    renderChart()
    const surface = surfaceOf()
    expect(screen.queryByTestId('chart-readout')).not.toBeInTheDocument()

    fireEvent.pointerMove(surface, { clientX: CHART.left, pointerType: 'mouse' })
    const readout = screen.getByTestId('chart-readout')
    expect(readout).toHaveTextContent('300')
    expect(readout).toHaveTextContent('measured')

    fireEvent.pointerMove(surface, { clientX: CHART.right, pointerType: 'mouse' })
    expect(screen.getByTestId('chart-readout')).toHaveTextContent('forecast')
    expect(screen.getByTestId('chart-readout')).toHaveTextContent('402')
    expect(screen.getByTestId('chart-readout')).toHaveTextContent('likely 378–432')

    fireEvent.pointerLeave(surface, { pointerType: 'mouse' })
    expect(screen.queryByTestId('chart-readout')).not.toBeInTheDocument()
  })

  it('keeps the readout after a touch ends, so a tap can be read', () => {
    renderChart()
    const surface = surfaceOf()
    fireEvent.pointerDown(surface, { clientX: CHART.left + 200, pointerType: 'touch' })
    fireEvent.pointerLeave(surface, { pointerType: 'touch' })
    expect(screen.getByTestId('chart-readout')).toBeInTheDocument()
  })

  it('switches to a table of the same numbers and back', async () => {
    const user = userEvent.setup()
    renderChart('pm25')
    await user.click(screen.getByRole('button', { name: 'View as table' }))

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(1 + 73 + 6)
    expect(within(table).getByRole('columnheader', { name: 'Likely range' })).toBeInTheDocument()
    const nowRow = within(table).getByRole('row', { name: /Now/ })
    expect(nowRow).toHaveTextContent('372')
    expect(screen.getByRole('region', { name: /Bawana: hourly values \(PM2.5, µg\/m³\)/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'View as chart' }))
    expect(screen.getByRole('img')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

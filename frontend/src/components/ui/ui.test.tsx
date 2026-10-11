import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { AqiScaleBar } from '../aqi/AqiScaleBar'
import { CategoryPill } from '../aqi/CategoryPill'
import { ErrorState } from './ErrorState'
import { ProgressBar } from './ProgressBar'
import { SegmentedControl } from './SegmentedControl'
import { StaleBanner } from './StaleBanner'

describe('CategoryPill', () => {
  it('names the CPCB category as text, not just colour', () => {
    render(<CategoryPill aqi={374} />)
    expect(screen.getByText('Very Poor')).toHaveClass('bg-aqi-very-poor-bg', 'text-aqi-very-poor-fg')
  })

  it('switches tier at the Severe line', () => {
    const { rerender } = render(<CategoryPill aqi={400} />)
    expect(screen.getByText('Very Poor')).toBeInTheDocument()
    rerender(<CategoryPill aqi={401} />)
    expect(screen.getByText('Severe')).toHaveClass('bg-aqi-severe-bg')
  })
})

describe('SegmentedControl', () => {
  function Harness() {
    const [value, setValue] = useState<'aqi' | 'pm25'>('aqi')
    return (
      <SegmentedControl
        label="Choose measure"
        value={value}
        onChange={setValue}
        options={[
          { value: 'aqi', label: 'AQI' },
          { value: 'pm25', label: 'PM2.5' },
        ]}
      />
    )
  }

  it('exposes the selection with aria-pressed and changes it on click', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    expect(screen.getByRole('group', { name: 'Choose measure' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AQI' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'PM2.5' }))
    expect(screen.getByRole('button', { name: 'PM2.5' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'AQI' })).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('AqiScaleBar', () => {
  it('describes itself to screen readers and positions the forecast marker', () => {
    const { container } = render(
      <AqiScaleBar now={356} forecast={374} range={{ lo: 325, hi: 431 }} label="Tomorrow falls in Very Poor" />,
    )
    expect(screen.getByRole('img', { name: 'Tomorrow falls in Very Poor' })).toBeInTheDocument()
    const marker = container.querySelector('[style*="left: 74.8%"]')
    expect(marker).not.toBeNull()
  })
})

describe('ProgressBar', () => {
  it('clamps out-of-range values and hides itself from assistive tech', () => {
    const { container } = render(<ProgressBar value={1.7} fillClassName="bg-aqi-severe" />)
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')
    expect(container.querySelector('.bg-aqi-severe')).toHaveStyle({ width: '100%' })
  })
})

describe('ErrorState and StaleBanner', () => {
  it('offers a retry that calls back', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<ErrorState message="The forecast service answered 503." onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('answered 503')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('tells the reader how old the data is', () => {
    render(<StaleBanner dataAsOf="2026-10-11T08:30:00Z" />)
    expect(screen.getByRole('status')).toHaveTextContent('14:00 IST on Sun 11 Oct')
  })
})

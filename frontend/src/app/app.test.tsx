import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAt } from '@/test/renderApp'

describe('app shell', () => {
  it('renders the overview with the section nav and a skip link', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { level: 1, name: /Forecast AQI 374/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main')

    const nav = screen.getAllByRole('navigation', { name: 'Sections' })[0] as HTMLElement
    const links = within(nav).getAllByRole('link')
    expect(links.map((l) => l.textContent)).toEqual(['Overview', 'Stations', 'Operations', 'Model health'])
    expect(within(nav).getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  })

  it('marks Stations current on a station sub-route', async () => {
    renderAt('/stations/anand-vihar')
    expect(await screen.findByRole('heading', { level: 1, name: 'Anand Vihar' })).toBeInTheDocument()
    const nav = screen.getAllByRole('navigation', { name: 'Sections' })[0] as HTMLElement
    expect(within(nav).getByRole('link', { name: 'Stations' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')
  })

  it('navigates between sections, updates the title and moves focus to the page', async () => {
    const user = userEvent.setup()
    renderAt('/')
    await screen.findByRole('heading', { level: 1, name: /Forecast AQI 374/ })

    const nav = screen.getAllByRole('navigation', { name: 'Sections' })[0] as HTMLElement
    await user.click(within(nav).getByRole('link', { name: 'Operations' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'GRAP outlook' })).toBeInTheDocument()
    expect(document.title).toBe('Operations · Delhi Air Forecast')
    expect(screen.getByRole('main')).toHaveFocus()
  })

  it('shows the sample-data badge and the update stamp from the health endpoint', async () => {
    renderAt('/')
    expect((await screen.findAllByText('Sample readings · live feed pending')).length).toBeGreaterThan(0)
    expect(await screen.findByText('Updated 14:00 IST · Sun 11 Oct')).toBeInTheDocument()
  })

  it('shows a 404 page for unknown addresses', async () => {
    renderAt('/nowhere')
    expect(await screen.findByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
  })

  it('opens the mobile menu as a dialog, navigates and closes it', async () => {
    const user = userEvent.setup()
    renderAt('/')
    await screen.findByRole('heading', { level: 1, name: /Forecast AQI 374/ })

    await user.click(screen.getByRole('button', { name: 'Open menu' }))
    const dialog = await screen.findByRole('dialog', { name: 'Menu' })
    await user.click(within(dialog).getByRole('link', { name: 'Model health' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Model health' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

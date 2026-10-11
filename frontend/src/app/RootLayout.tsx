import { useEffect, useRef } from 'react'
import { Outlet, useLocation, useMatches } from 'react-router-dom'
import { SiteHeader } from '@/components/layout/SiteHeader'
import { SkipLink } from '@/components/layout/SkipLink'

const SITE_NAME = 'Delhi Air Forecast'

function sectionOf(pathname: string): string {
  return pathname.split('/')[1] ?? ''
}

/** Route `handle: { title }` of the deepest match that has one. */
function useRouteTitle(): string | undefined {
  const matches = useMatches()
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as { title?: string } | undefined
    if (handle?.title) return handle.title
  }
  return undefined
}

export function RootLayout() {
  const { pathname } = useLocation()
  const title = useRouteTitle()
  const mainRef = useRef<HTMLElement>(null)
  const lastSection = useRef(sectionOf(pathname))

  useEffect(() => {
    document.title = title ? `${title} · ${SITE_NAME}` : SITE_NAME
  }, [title])

  // Moving between sections hands focus to the new page for screen-reader and
  // keyboard users. Switching station inside /stations must not steal focus
  // from the station pill being used.
  useEffect(() => {
    const section = sectionOf(pathname)
    if (section === lastSection.current) return
    lastSection.current = section
    mainRef.current?.focus({ preventScroll: true })
    window.scrollTo({ top: 0 })
  }, [pathname])

  return (
    <div className="min-h-dvh">
      <SkipLink />
      <SiteHeader />
      <main id="main" ref={mainRef} tabIndex={-1} className="outline-none">
        <Outlet />
      </main>
    </div>
  )
}

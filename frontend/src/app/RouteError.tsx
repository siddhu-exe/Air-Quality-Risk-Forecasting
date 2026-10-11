import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom'
import { ErrorState } from '@/components/ui/ErrorState'
import { Page } from '@/components/ui/Page'

/** Catches render errors and failed route-chunk loads. */
export function RouteError() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />

  console.error(error)
  return (
    <Page>
      <ErrorState
        title="Something went wrong"
        message="This page failed to load. Reloading usually fixes it."
        onRetry={() => window.location.reload()}
      />
    </Page>
  )
}

export function NotFound() {
  return (
    <Page className="items-start gap-4 pt-10">
      <p className="text-13 uppercase tracking-caps text-ink-muted">Error 404</p>
      <h1 className="font-serif text-56 leading-none">Page not found</h1>
      <p className="text-ink-2">That address does not match a page here.</p>
      <Link to="/" className="link">
        Back to the overview
      </Link>
    </Page>
  )
}

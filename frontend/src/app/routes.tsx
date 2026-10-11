import type { RouteObject } from 'react-router-dom'
import { HydrateFallback } from './HydrateFallback'
import { NotFound, RouteError } from './RouteError'
import { RootLayout } from './RootLayout'

/**
 * Each page is its own chunk, so the first visit downloads only what it shows.
 * `handle.title` feeds the document title (see RootLayout).
 */
export const routes: RouteObject[] = [
  {
    path: '/',
    element: <RootLayout />,
    errorElement: <RouteError />,
    HydrateFallback,
    children: [
      {
        index: true,
        handle: { title: 'Overview' },
        lazy: async () => ({ Component: (await import('@/features/overview/OverviewPage')).OverviewPage }),
      },
      {
        // The station id is optional: /stations picks the first station.
        path: 'stations/:stationId?',
        handle: { title: 'Stations' },
        lazy: async () => ({ Component: (await import('@/features/stations/StationsPage')).StationsPage }),
      },
      {
        path: 'operations',
        handle: { title: 'Operations' },
        lazy: async () => ({ Component: (await import('@/features/operations/OperationsPage')).OperationsPage }),
      },
      {
        path: 'model-health',
        handle: { title: 'Model health' },
        lazy: async () => ({
          Component: (await import('@/features/model-health/ModelHealthPage')).ModelHealthPage,
        }),
      },
      { path: '*', handle: { title: 'Page not found' }, element: <NotFound /> },
    ],
  },
]

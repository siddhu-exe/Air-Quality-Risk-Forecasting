import { QueryClient } from '@tanstack/react-query'

/** Forecasts are issued hourly, so five minutes of staleness is invisible to users. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  })
}

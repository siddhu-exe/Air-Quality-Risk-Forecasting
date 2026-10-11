import { env } from '@/config/env'
import { createHttpClient } from './http'
import { createMockClient } from './mock/client'
import type { ApiClient } from './types'

/** The app-wide client: sample data until the live API exists (VITE_USE_MOCK). */
export const api: ApiClient = env.useMock
  ? // A little latency in dev so loading states are visible; none in builds or tests.
    createMockClient({ latencyMs: import.meta.env.MODE === 'development' ? 250 : 0 })
  : createHttpClient()

export const usingMockData = env.useMock

export { ApiError } from './http'
export type { ApiClient } from './types'

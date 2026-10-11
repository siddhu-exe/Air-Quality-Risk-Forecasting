import { z } from 'zod'

const schema = z.object({
  VITE_API_BASE_URL: z.string().min(1).default('/api/v1'),
  VITE_USE_MOCK: z.enum(['true', 'false']).default('true'),
})

/** Parses a raw env record; exported separately so it can be tested. */
export function parseEnv(raw: Record<string, unknown>) {
  const parsed = schema.parse(raw)
  return {
    /** No trailing slash, so callers can append `/overview`. */
    apiBaseUrl: parsed.VITE_API_BASE_URL.replace(/\/+$/, ''),
    /** True until the live API exists; flip with VITE_USE_MOCK=false. */
    useMock: parsed.VITE_USE_MOCK === 'true',
  }
}

export const env = parseEnv(import.meta.env)

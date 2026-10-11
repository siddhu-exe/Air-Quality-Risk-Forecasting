import { parseEnv } from './env'

describe('parseEnv', () => {
  it('defaults to mock data on the relative API path', () => {
    expect(parseEnv({})).toEqual({ apiBaseUrl: '/api/v1', useMock: true })
  })

  it('strips trailing slashes and honours VITE_USE_MOCK=false', () => {
    expect(
      parseEnv({ VITE_API_BASE_URL: 'https://api.example.org/api/v1//', VITE_USE_MOCK: 'false' }),
    ).toEqual({ apiBaseUrl: 'https://api.example.org/api/v1', useMock: false })
  })

  it('rejects an unrecognised VITE_USE_MOCK value instead of guessing', () => {
    expect(() => parseEnv({ VITE_USE_MOCK: 'yes' })).toThrow()
  })
})

import { z } from 'zod'
import { ApiError, getJson } from './http'

const schema = z.object({ ok: z.literal(true) })
const baseUrl = 'https://api.test/api/v1'

function stubFetch(impl: () => Promise<Response>) {
  const fetchMock = vi.fn(impl)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('getJson', () => {
  it('requests the path under the base URL and returns parsed data', async () => {
    const fetchMock = stubFetch(async () => Response.json({ ok: true }))
    await expect(getJson('/health', schema, { baseUrl })).resolves.toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith('https://api.test/api/v1/health', expect.any(Object))
  })

  it('turns an HTTP error into an ApiError carrying the status', async () => {
    stubFetch(async () => new Response('nope', { status: 503 }))
    const error = await getJson('/health', schema, { baseUrl }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
  })

  it('turns a network failure into a friendly ApiError', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    await expect(getJson('/health', schema, { baseUrl })).rejects.toThrow('Could not reach')
  })

  it('rejects a body that does not match the schema, and says so in the console', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    stubFetch(async () => Response.json({ ok: false }))
    await expect(getJson('/health', schema, { baseUrl })).rejects.toThrow('unexpected shape')
    expect(consoleError).toHaveBeenCalled()
  })

  it('rejects a body that is not JSON', async () => {
    stubFetch(async () => new Response('<html>', { status: 200 }))
    await expect(getJson('/health', schema, { baseUrl })).rejects.toThrow('unreadable')
  })

  it('lets an aborted request surface as an AbortError, not an ApiError', async () => {
    stubFetch(async () => {
      throw new DOMException('aborted', 'AbortError')
    })
    await expect(getJson('/health', schema, { baseUrl })).rejects.toMatchObject({ name: 'AbortError' })
  })
})

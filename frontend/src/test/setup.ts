import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

/**
 * React Router's data router builds `new Request(url, { signal })` on every
 * navigation. jsdom's AbortSignal fails Node's (undici) brand check there, so
 * the Request is built without it and the jsdom signal is attached afterwards;
 * aborts still reach loaders. Test-only; browsers are unaffected.
 */
const NodeRequest = globalThis.Request
class JsdomSafeRequest extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const { signal, ...rest } = init ?? {}
    super(input, rest)
    if (signal) Object.defineProperty(this, 'signal', { value: signal })
  }
}
globalThis.Request = JsdomSafeRequest as typeof Request

// jsdom does not implement scrolling; the layout scrolls to the top on section change.
window.scrollTo = vi.fn()

afterEach(() => {
  cleanup()
})

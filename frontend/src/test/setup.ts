import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
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

// jsdom has no PointerEvent, so fireEvent.pointerMove would drop clientX and pointerType.
if (!('PointerEvent' in window)) {
  class PointerEventPolyfill extends MouseEvent {
    readonly pointerType: string
    constructor(type: string, init: PointerEventInit = {}) {
      super(type, init)
      this.pointerType = init.pointerType ?? 'mouse'
    }
  }
  Object.defineProperty(window, 'PointerEvent', { value: PointerEventPolyfill, configurable: true })
}

// jsdom does not implement scrolling; the layout scrolls to the top on section change.
window.scrollTo = vi.fn()

// The first visit to each lazy page transforms its module graph, which can
// take over Testing Library's 1 s default under jsdom.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})

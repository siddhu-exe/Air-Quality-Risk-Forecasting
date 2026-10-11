import { ApiError } from './http'

/** A sentence a person can act on; never a stack trace or a status code alone. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'That item does not exist in the forecast service.'
    return `${error.message} Check your connection and try again.`
  }
  return 'Something went wrong while loading this section. Try again in a moment.'
}

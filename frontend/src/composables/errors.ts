import { ApiError } from '../services/http'

// Composables show errors as {code, title, message}; anything that is not an ApiError (a bug
// in the frontend) is reported as a generic one instead of escaping as an unhandled rejection.
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  console.error(error)
  return new ApiError(0, 'Something went wrong', 'Reload the page and try again.')
}

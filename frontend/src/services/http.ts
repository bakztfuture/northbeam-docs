// The one place that calls fetch. Every non-2xx response, and a request that never reaches
// the API, is thrown as an ApiError.

export class ApiError extends Error {
  readonly code: number
  readonly title: string

  // `message` is the API's optional message, or '' when it sent none.
  constructor(code: number, title: string, message = '') {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.title = title
  }
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server', 'Check your connection and try again.')
  }

  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

// Known errors arrive as the flat {code, title, message?} body. Anything else (FastAPI's 422
// body, or a non-JSON proxy error) falls back to the HTTP status.
async function toApiError(response: Response): Promise<ApiError> {
  const fallback = response.status === 422 ? 'Invalid request' : 'Request failed'
  try {
    const data = await response.json()
    if (typeof data?.title === 'string') {
      return new ApiError(response.status, data.title, data.message ?? '')
    }
  } catch {
    // Not JSON; use the fallback below.
  }
  return new ApiError(response.status, fallback)
}

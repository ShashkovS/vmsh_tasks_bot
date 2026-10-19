import { useAuthentication } from '@vmsh/app-shell'
import { apiErrorSchema, ApiResponseError } from '@vmsh/contracts'

/** Optional AI requests must not trigger the global service-availability overlay. */
export function useAiReviewRequest() {
  const auth = useAuthentication()
  return async (path: string, init?: RequestInit): Promise<unknown> => {
    const request = () =>
      fetch(`${auth.client.runtime.apiBase}${path}`, {
        ...init,
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: { 'Content-Type': 'application/json', ...init?.headers },
      })
    let response = await request()
    if (response.status === 401) {
      await auth.refresh()
      response = await request()
    }
    const payload: unknown = await response.json()
    if (!response.ok) {
      const error = new ApiResponseError(response.status, apiErrorSchema.parse(payload))
      auth.handleApiError(error)
      throw error
    }
    return payload
  }
}

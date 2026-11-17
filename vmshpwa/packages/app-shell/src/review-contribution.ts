import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  pwaFetch,
  reviewContributionQuerySchema,
  reviewContributionSchema,
  type ReviewContributionQuery,
  type RuntimeConfig,
} from '@vmsh/contracts'

/** Staff transport; docs/review-contribution.md. */
export function createReviewContributionClient(
  runtime: RuntimeConfig,
  options: {
    refreshSession?: () => Promise<unknown>
    fetchImplementation?: typeof globalThis.fetch
  } = {},
) {
  const base = parseRuntimeConfigForAudience('staff', runtime).apiBase
  return async (query: ReviewContributionQuery, signal?: AbortSignal) => {
    const parsed = reviewContributionQuerySchema.parse(query)
    const params = new URLSearchParams()
    if (parsed.course !== undefined) params.set('course', parsed.course)
    if (parsed.lesson !== undefined) params.set('lesson', String(parsed.lesson))
    if (parsed.groupLesson !== undefined) params.set('groupLesson', parsed.groupLesson)
    const send = () =>
      (options.fetchImplementation ?? pwaFetch)(`${base}/review/my-contribution?${params}`, {
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: { Accept: 'application/json' },
        ...(signal ? { signal } : {}),
      })
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return reviewContributionSchema.parse(payload)
  }
}

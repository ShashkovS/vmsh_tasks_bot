import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  problemReleaseRequestSchema,
  problemReleaseResponseSchema,
  pwaFetch,
  type ProblemReleaseRequest,
  type ProblemReleaseResponse,
  type RuntimeConfig,
} from '@vmsh/contracts'

/** Group-scoped Staff transport; docs/problem-release.md. */
export function createProblemReleaseClient(
  runtime: RuntimeConfig,
  refresh: () => Promise<unknown>,
) {
  const config = parseRuntimeConfigForAudience('staff', runtime)
  const request = async (
    groupLessonId: string,
    revisionId: string,
    input?: ProblemReleaseRequest,
    etag?: string,
    signal?: AbortSignal,
  ): Promise<ProblemReleaseResponse> => {
    const path = `/group-lessons/${encodeURIComponent(publicIdSchema.parse(groupLessonId))}/problem-release`
    const url =
      config.apiBase +
      path +
      (input ? '' : `?revisionId=${encodeURIComponent(publicIdSchema.parse(revisionId))}`)
    const send = () =>
      pwaFetch(url, {
        method: input ? 'PUT' : 'GET',
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(input ? { 'Content-Type': 'application/json', 'If-Match': etag! } : {}),
        },
        ...(input ? { body: JSON.stringify(problemReleaseRequestSchema.parse(input)) } : {}),
        ...(signal ? { signal } : {}),
      })
    let response = await send()
    if (response.status === 401) {
      await response.body?.cancel()
      await refresh()
      response = await send()
    }
    if (!response.ok)
      throw new ApiResponseError(response.status, apiErrorSchema.parse(await response.json()))
    return problemReleaseResponseSchema.parse(await response.json())
  }
  return {
    get: (lessonId: string, revisionId: string, signal?: AbortSignal) =>
      request(lessonId, revisionId, undefined, undefined, signal),
    save: (lessonId: string, etag: string, input: ProblemReleaseRequest) =>
      request(lessonId, input.conditionRevisionId, input, etag),
  }
}
export type ProblemReleaseClient = ReturnType<typeof createProblemReleaseClient>

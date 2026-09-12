import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  problemSynonymCandidatesResponseSchema,
  problemSynonymImpactRequestSchema,
  problemSynonymImpactResponseSchema,
  problemSynonymMergeRequestSchema,
  problemSynonymQueryKeys,
  problemSynonymSplitRequestSchema,
  publicIdSchema,
  type PrincipalQueryScope,
  type ProblemSynonymCandidatesResponse,
  type ProblemSynonymImpactRequest,
  type ProblemSynonymImpactResponse,
  type ProblemSynonymMergeRequest,
  type ProblemSynonymSplitRequest,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface ProblemSynonymClient {
  candidates(
    courseLessonId: string,
    options?: { signal?: AbortSignal },
  ): Promise<ProblemSynonymCandidatesResponse>
  preview(request: ProblemSynonymImpactRequest): Promise<ProblemSynonymImpactResponse>
  merge(request: ProblemSynonymMergeRequest): Promise<ProblemSynonymImpactResponse>
  split(
    synonymId: string,
    request: ProblemSynonymSplitRequest,
  ): Promise<ProblemSynonymImpactResponse>
}

/** Direct Staff API adapter for the Phase-10 synonym screen. */
export function createProblemSynonymClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): ProblemSynonymClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function request(path: string, init: RequestInit): Promise<unknown> {
    const send = () =>
      fetchImplementation(`${configured.apiBase}${path}`, {
        cache: 'no-store',
        credentials: 'include',
        redirect: 'error',
        ...init,
        headers: {
          Accept: 'application/json',
          ...(init.body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...init.headers,
        },
      })
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }

  const post = (path: string, body: object) =>
    request(path, { method: 'POST', body: JSON.stringify(body) }).then((payload) =>
      problemSynonymImpactResponseSchema.parse(payload),
    )

  return {
    async candidates(rawCourseLessonId, { signal } = {}) {
      const courseLessonId = publicIdSchema.parse(rawCourseLessonId)
      return problemSynonymCandidatesResponseSchema.parse(
        await request(`/course-lessons/${encodeURIComponent(courseLessonId)}/synonym-candidates`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    preview(input) {
      return post(
        '/problem-synonyms/impact-preview',
        problemSynonymImpactRequestSchema.parse(input),
      )
    },
    merge(input) {
      return post('/problem-synonyms/merge', problemSynonymMergeRequestSchema.parse(input))
    },
    split(rawSynonymId, input) {
      const synonymId = publicIdSchema.parse(rawSynonymId)
      return post(
        `/problem-synonyms/${encodeURIComponent(synonymId)}/split`,
        problemSynonymSplitRequestSchema.parse(input),
      )
    },
  }
}

export function useProblemSynonymCandidatesQuery(
  client: ProblemSynonymClient,
  principal: PrincipalQueryScope,
  courseLessonId: string,
  enabled = true,
) {
  return useQuery({
    queryKey: problemSynonymQueryKeys.lesson(principal, courseLessonId),
    queryFn: ({ signal }) => client.candidates(courseLessonId, { signal }),
    enabled,
  })
}

import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  oralResultQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  recordOralResultRequestSchema,
  recordOralResultResponseSchema,
  staffOralRosterResponseSchema,
  type PrincipalQueryScope,
  type RecordOralResultRequest,
  type RecordOralResultResponse,
  type RuntimeConfig,
  type StaffOralRosterResponse,
} from '@vmsh/contracts'

export function createStaffOralResultClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
) {
  const base = parseRuntimeConfigForAudience('staff', runtime).apiBase
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  const request = async (path: string, init: RequestInit): Promise<unknown> => {
    const send = () =>
      fetchImplementation(`${base}${path}`, {
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

  return {
    async roster(groupLessonId: string, signal?: AbortSignal): Promise<StaffOralRosterResponse> {
      const lessonId = publicIdSchema.parse(groupLessonId)
      return staffOralRosterResponseSchema.parse(
        await request(`/group-lessons/${encodeURIComponent(lessonId)}/oral-roster`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async record(
      groupLessonId: string,
      input: RecordOralResultRequest,
    ): Promise<RecordOralResultResponse> {
      const lessonId = publicIdSchema.parse(groupLessonId)
      return recordOralResultResponseSchema.parse(
        await request(`/group-lessons/${encodeURIComponent(lessonId)}/oral-results`, {
          method: 'POST',
          body: JSON.stringify(recordOralResultRequestSchema.parse(input)),
        }),
      )
    },
  }
}

export function useStaffOralRosterQuery(
  client: ReturnType<typeof createStaffOralResultClient>,
  principal: PrincipalQueryScope,
  groupLessonId: string,
  enabled = true,
) {
  return useQuery({
    enabled,
    queryKey: oralResultQueryKeys.staffRoster(principal, groupLessonId),
    queryFn: ({ signal }) => client.roster(groupLessonId, signal),
    meta: { realtimeResources: ['oral-results'] },
  })
}

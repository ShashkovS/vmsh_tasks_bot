import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  oralWindowJoinResponseSchema,
  oralWindowQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  studentOralWindowListResponseSchema,
  type OralWindowJoinResponse,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type StudentOralWindowListResponse,
} from '@vmsh/contracts'

export function createStudentOralWindowClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
) {
  const base = parseRuntimeConfigForAudience('student', runtime).apiBase
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  const request = async (path: string, signal?: AbortSignal): Promise<unknown> => {
    const send = () =>
      fetchImplementation(`${base}${path}`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
        ...(signal === undefined ? {} : { signal }),
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

  const path = (courseId: string, groupLessonId: string) =>
    `/courses/${encodeURIComponent(publicIdSchema.parse(courseId))}/lessons/` +
    `${encodeURIComponent(publicIdSchema.parse(groupLessonId))}/oral-windows`

  return {
    async list(
      courseId: string,
      groupLessonId: string,
      signal?: AbortSignal,
    ): Promise<StudentOralWindowListResponse> {
      return studentOralWindowListResponseSchema.parse(
        await request(path(courseId, groupLessonId), signal),
      )
    },
    async join(
      courseId: string,
      groupLessonId: string,
      windowId: string,
      signal?: AbortSignal,
    ): Promise<OralWindowJoinResponse> {
      return oralWindowJoinResponseSchema.parse(
        await request(
          `${path(courseId, groupLessonId)}/${encodeURIComponent(
            publicIdSchema.parse(windowId),
          )}/join`,
          signal,
        ),
      )
    },
  }
}

export function useStudentOralWindowsQuery(
  client: ReturnType<typeof createStudentOralWindowClient>,
  principal: PrincipalQueryScope,
  courseId: string,
  groupLessonId: string,
) {
  return useQuery({
    queryKey: oralWindowQueryKeys.student(principal, courseId, groupLessonId),
    queryFn: ({ signal }) => client.list(courseId, groupLessonId, signal),
    meta: { realtimeResources: ['oral-windows'] },
  })
}

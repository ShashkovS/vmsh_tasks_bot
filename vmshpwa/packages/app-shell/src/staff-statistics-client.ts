import { pwaFetch } from '@vmsh/contracts'
import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  statisticsRecalculationRequestSchema,
  statisticsRecalculationSchema,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  staffStatisticsQueryKey,
  staffStatisticsResponseSchema,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type StaffStatisticsResponse,
} from '@vmsh/contracts'

export interface StaffStatisticsFilter {
  courseId: string | null
  groupId: string | null
  lessonNumber?: number | null
  studentId?: string | null
}

export interface StaffStatisticsClient {
  get(filter: StaffStatisticsFilter, signal?: AbortSignal): Promise<StaffStatisticsResponse>
}

export function createStaffStatisticsClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): StaffStatisticsClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? pwaFetch

  return {
    async get(filter, signal) {
      const search = new URLSearchParams()
      if (filter.courseId !== null) search.set('courseId', publicIdSchema.parse(filter.courseId))
      if (filter.groupId !== null) search.set('groupId', publicIdSchema.parse(filter.groupId))
      if (filter.lessonNumber != null) search.set('lessonNumber', String(filter.lessonNumber))
      if (filter.studentId) search.set('studentId', publicIdSchema.parse(filter.studentId))
      const path = `/statistics${search.size === 0 ? '' : `?${search}`}`
      const request = () =>
        fetchImplementation(`${configured.apiBase}${path}`, {
          method: 'GET',
          cache: 'no-store',
          credentials: 'include',
          redirect: 'error',
          headers: { Accept: 'application/json' },
          ...(signal === undefined ? {} : { signal }),
        })
      let response = await request()
      if (response.status === 401 && options.refreshSession) {
        await response.body?.cancel()
        await options.refreshSession()
        response = await request()
      }
      const payload: unknown = await response.json()
      if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
      return staffStatisticsResponseSchema.parse(payload)
    },
  }
}

export function useStaffStatisticsQuery(
  client: StaffStatisticsClient,
  principal: PrincipalQueryScope,
  filter: StaffStatisticsFilter,
) {
  return useQuery({
    queryKey: [
      ...staffStatisticsQueryKey(principal, filter.courseId, filter.groupId),
      filter.lessonNumber ?? null,
      filter.studentId ?? null,
    ],
    refetchOnWindowFocus: 'always',
    queryFn: ({ signal }) => client.get(filter, signal),
  })
}

/** Admin calculation transport; shares the regular same-origin CSRF boundary. */
export function createStatisticsRecalculationClient(
  runtime: RuntimeConfig,
  refreshSession: () => Promise<unknown>,
) {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  return async (courseId: string, idempotencyKey?: string) => {
    const body = idempotencyKey
      ? statisticsRecalculationRequestSchema.parse({ courseId, idempotencyKey })
      : undefined
    const request = () =>
      pwaFetch(
        `${configured.apiBase}/statistics/recalculate${body ? '' : `?courseId=${encodeURIComponent(publicIdSchema.parse(courseId))}`}`,
        {
          method: body ? 'POST' : 'GET',
          credentials: 'include',
          cache: 'no-store',
          redirect: 'error',
          headers: {
            Accept: 'application/json',
            ...(body ? { 'Content-Type': 'application/json' } : {}),
          },
          ...(body ? { body: JSON.stringify(body) } : {}),
        },
      )
    let response = await request()
    if (response.status === 401) {
      await response.body?.cancel()
      await refreshSession()
      response = await request()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return statisticsRecalculationSchema.parse(payload)
  }
}

import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  pwaFetch,
  publicIdSchema,
  statisticsSummarySchema,
  statisticsPlusTableSchema,
  type RuntimeConfig,
  type PrincipalQueryScope,
  principalQueryKey,
} from '@vmsh/contracts'

/** Lazy per-tab reads; docs/lesson-statistics.md, staff-statistics-reports.tsx. */
export function createStatisticsReportsClient(
  runtime: RuntimeConfig,
  options: {
    refreshSession?: () => Promise<unknown>
    fetchImplementation?: typeof globalThis.fetch
  } = {},
) {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  return async (
    kind: 'summary' | 'plus-table',
    filter: {
      courseId: string | null
      groupId: string | null
      lessonNumber: number | null
    },
    signal?: AbortSignal,
  ) => {
    const search = new URLSearchParams()
    if (filter.courseId) search.set('courseId', publicIdSchema.parse(filter.courseId))
    if (filter.groupId) search.set('groupId', publicIdSchema.parse(filter.groupId))
    if (kind === 'plus-table' && filter.lessonNumber !== null)
      search.set('lessonNumber', String(filter.lessonNumber))
    const request = () =>
      (options.fetchImplementation ?? pwaFetch)(
        `${configured.apiBase}/statistics/${kind}?${search}`,
        {
          method: 'GET',
          credentials: 'include',
          cache: 'no-store',
          redirect: 'error',
          headers: { Accept: 'application/json' },
          ...(signal ? { signal } : {}),
        },
      )
    let response = await request()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await request()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return kind === 'summary'
      ? statisticsSummarySchema.parse(payload)
      : statisticsPlusTableSchema.parse(payload)
  }
}

export function useStatisticsReportQuery(
  client: ReturnType<typeof createStatisticsReportsClient>,
  principal: PrincipalQueryScope,
  kind: 'summary' | 'plus-table',
  filter: { courseId: string | null; groupId: string | null; lessonNumber: number | null },
) {
  return useQuery({
    queryKey: [
      ...principalQueryKey(principal),
      'statistics-report',
      kind,
      filter.courseId,
      filter.groupId,
      kind === 'plus-table' ? filter.lessonNumber : null,
    ],
    queryFn: ({ signal }) => client(kind, filter, signal),
    refetchOnWindowFocus: 'always',
  })
}

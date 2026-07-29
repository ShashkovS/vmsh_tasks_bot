import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  familyChildCoursesResponseSchema,
  familyCourseQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  type FamilyChildCoursesResponse,
  type PrincipalQueryScope,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface FamilyCourseClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface FamilyCourseClient {
  childCourses(studentId: string, signal?: AbortSignal): Promise<FamilyChildCoursesResponse>
}

/** Small same-origin client for the Phase-9 Family child summary. */
export function createFamilyCourseClient(
  runtime: RuntimeConfig,
  options: FamilyCourseClientOptions = {},
): FamilyCourseClient {
  const familyRuntime = parseRuntimeConfigForAudience('family', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function send(studentId: string, signal?: AbortSignal): Promise<Response> {
    return fetchImplementation(
      `${familyRuntime.apiBase}/children/${encodeURIComponent(studentId)}/courses`,
      {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
        ...(signal === undefined ? {} : { signal }),
      },
    )
  }

  return {
    async childCourses(studentId, signal) {
      const parsedStudentId = publicIdSchema.parse(studentId)
      let response = await send(parsedStudentId, signal)
      if (response.status === 401 && options.refreshSession) {
        await response.body?.cancel()
        await options.refreshSession()
        response = await send(parsedStudentId, signal)
      }
      if (!response.ok) {
        let payload: unknown
        try {
          payload = await response.json()
        } catch {
          throw new Error('Family course API returned an invalid error response')
        }
        throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
      }
      let payload: unknown
      try {
        payload = await response.json()
      } catch (error) {
        throw new Error('Family course API returned malformed JSON', { cause: error })
      }
      return familyChildCoursesResponseSchema.parse(payload)
    },
  }
}

export function useFamilyChildCoursesQuery(
  client: FamilyCourseClient,
  principal: PrincipalQueryScope,
  studentId: string,
  enabled = true,
) {
  return useQuery({
    queryKey: familyCourseQueryKeys.child(principal, studentId),
    queryFn: ({ signal }) => client.childCourses(studentId, signal),
    enabled,
  })
}

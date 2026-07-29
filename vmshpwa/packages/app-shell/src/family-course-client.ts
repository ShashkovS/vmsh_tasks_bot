import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  familyChildCoursesResponseSchema,
  familyChildHomeResponseSchema,
  familyCourseQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  type FamilyChildCoursesResponse,
  type FamilyChildHomeResponse,
  type PrincipalQueryScope,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface FamilyCourseClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface FamilyCourseClient {
  childCourses(studentId: string, signal?: AbortSignal): Promise<FamilyChildCoursesResponse>
  childHome(studentId: string, signal?: AbortSignal): Promise<FamilyChildHomeResponse>
}

interface Parser<T> {
  parse(value: unknown): T
}

/** Small same-origin client for the Phase-9 Family child summary. */
export function createFamilyCourseClient(
  runtime: RuntimeConfig,
  options: FamilyCourseClientOptions = {},
): FamilyCourseClient {
  const familyRuntime = parseRuntimeConfigForAudience('family', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function request<T>(
    studentId: string,
    resource: 'courses' | 'home',
    parser: Parser<T>,
    signal?: AbortSignal,
  ): Promise<T> {
    const parsedStudentId = publicIdSchema.parse(studentId)
    const send = () =>
      fetchImplementation(
        `${familyRuntime.apiBase}/children/${encodeURIComponent(parsedStudentId)}/${resource}`,
        {
          method: 'GET',
          cache: 'no-store',
          credentials: 'include',
          headers: { Accept: 'application/json' },
          redirect: 'error',
          ...(signal === undefined ? {} : { signal }),
        },
      )
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
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
    return parser.parse(payload)
  }

  return {
    childCourses(studentId, signal) {
      return request(studentId, 'courses', familyChildCoursesResponseSchema, signal)
    },
    childHome(studentId, signal) {
      return request(studentId, 'home', familyChildHomeResponseSchema, signal)
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

export function useFamilyChildHomeQuery(
  client: FamilyCourseClient,
  principal: PrincipalQueryScope,
  studentId: string,
  enabled = true,
) {
  return useQuery({
    queryKey: familyCourseQueryKeys.home(principal, studentId),
    queryFn: ({ signal }) => client.childHome(studentId, signal),
    enabled,
  })
}

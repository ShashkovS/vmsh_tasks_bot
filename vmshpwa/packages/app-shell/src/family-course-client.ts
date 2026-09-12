import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  familyChildCoursesResponseSchema,
  familyWorksheetResponseSchema,
  type FamilyWorksheetResponse,
  familyChildHomeResponseSchema,
  familyCourseQueryKeys,
  familyEnrollmentUpdateRequestSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  courseEnrollmentSchema,
  type CourseEnrollment,
  type FamilyEnrollmentUpdateRequest,
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
  worksheet(
    studentId: string,
    courseId: string,
    groupId: string,
    lessonNumber: number,
    signal?: AbortSignal,
  ): Promise<FamilyWorksheetResponse>
  childCourses(studentId: string, signal?: AbortSignal): Promise<FamilyChildCoursesResponse>
  childHome(studentId: string, signal?: AbortSignal): Promise<FamilyChildHomeResponse>
  updateEnrollment(
    studentId: string,
    courseId: string,
    input: FamilyEnrollmentUpdateRequest,
  ): Promise<CourseEnrollment>
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
    resource: string,
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
    async worksheet(studentId, courseId, groupId, lessonNumber, signal) {
      if (!Number.isSafeInteger(lessonNumber) || lessonNumber < 0)
        throw new TypeError('Invalid lesson number')
      const result = await request(
        studentId,
        `courses/${encodeURIComponent(publicIdSchema.parse(courseId))}/lessons/${lessonNumber}?group=${encodeURIComponent(publicIdSchema.parse(groupId))}`,
        familyWorksheetResponseSchema,
        signal,
      )
      if (
        result.studentId !== studentId ||
        result.lesson.courseId !== courseId ||
        result.lesson.groupId !== groupId ||
        result.lesson.lessonNumber !== lessonNumber
      )
        throw new TypeError('Unexpected worksheet context')
      return result
    },
    childCourses(studentId, signal) {
      return request(studentId, 'courses', familyChildCoursesResponseSchema, signal)
    },
    childHome(studentId, signal) {
      return request(studentId, 'home', familyChildHomeResponseSchema, signal)
    },
    async updateEnrollment(studentId, courseId, input) {
      const parsedStudentId = publicIdSchema.parse(studentId)
      const parsedCourseId = publicIdSchema.parse(courseId)
      const parsedInput = familyEnrollmentUpdateRequestSchema.parse(input)
      const send = () =>
        fetchImplementation(
          `${familyRuntime.apiBase}/children/${encodeURIComponent(parsedStudentId)}/courses/${encodeURIComponent(parsedCourseId)}/enrollment`,
          {
            method: 'PATCH',
            credentials: 'include',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            redirect: 'error',
            body: JSON.stringify(parsedInput),
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
      return courseEnrollmentSchema.parse(await response.json())
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

export function useFamilyEnrollmentMutation(
  client: FamilyCourseClient,
  principal: PrincipalQueryScope,
  studentId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ courseId, input }: { courseId: string; input: FamilyEnrollmentUpdateRequest }) =>
      client.updateEnrollment(studentId, courseId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: familyCourseQueryKeys.home(principal, studentId),
      })
    },
  })
}

export function useFamilyWorksheetQuery(
  client: FamilyCourseClient,
  principal: PrincipalQueryScope,
  studentId: string,
  courseId: string,
  groupId: string,
  lessonNumber: number,
  enabled = true,
) {
  return useQuery({
    queryKey: [
      ...familyCourseQueryKeys.home(principal, studentId),
      'worksheet',
      courseId,
      groupId,
      lessonNumber,
    ],
    queryFn: ({ signal }) => client.worksheet(studentId, courseId, groupId, lessonNumber, signal),
    enabled,
  })
}

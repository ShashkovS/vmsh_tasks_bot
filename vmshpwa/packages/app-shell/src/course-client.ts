import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  courseEnrollmentSchema,
  courseQueryKeys,
  lessonCursorSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  studentHomeResponseSchema,
  studentLessonListResponseSchema,
  studentLessonSummarySchema,
  studentCourseAccessResponseSchema,
  type CourseEnrollment,
  type LessonCursor,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type StudentCourseAccessResponse,
  type StudentHomeResponse,
  type StudentLessonListResponse,
  type StudentLessonSummary,
} from '@vmsh/contracts'

/**
 * Same-origin Student course/access transport for Phase 3.
 * URL context never grants access; the server projects its revalidated session
 * authority. See `dev/development-plan/07-phase-3-student-reading.md`.
 */

export interface CourseRequestOptions {
  signal?: AbortSignal
}

export interface StudentLessonListOptions extends CourseRequestOptions {
  groupId?: string
  cursor?: LessonCursor
}

export interface StudentCourseClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface StudentCourseClient {
  readonly runtime: RuntimeConfig
  home(options?: CourseRequestOptions): Promise<StudentHomeResponse>
  list(options?: CourseRequestOptions): Promise<StudentCourseAccessResponse>
  enrollment(courseId: string, options?: CourseRequestOptions): Promise<CourseEnrollment>
  lessons(courseId: string, options?: StudentLessonListOptions): Promise<StudentLessonListResponse>
  lesson(
    courseId: string,
    groupLessonId: string,
    options?: CourseRequestOptions,
  ): Promise<StudentLessonSummary>
}

export class CourseProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'CourseProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class CourseNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Course request could not reach the server', { cause: options.cause })
    this.name = 'CourseNetworkError'
  }
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

class BrowserStudentCourseClient implements StudentCourseClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: StudentCourseClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('student', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async home(options: CourseRequestOptions = {}): Promise<StudentHomeResponse> {
    return this.#request('/home', options, studentHomeResponseSchema)
  }

  async list(options: CourseRequestOptions = {}): Promise<StudentCourseAccessResponse> {
    return this.#request('/courses', options, studentCourseAccessResponseSchema)
  }

  async enrollment(
    courseId: string,
    options: CourseRequestOptions = {},
  ): Promise<CourseEnrollment> {
    const parsedCourseId = publicIdSchema.parse(courseId)
    return this.#request(
      `/courses/${encodeURIComponent(parsedCourseId)}/enrollment`,
      options,
      courseEnrollmentSchema,
    )
  }

  async lessons(
    courseId: string,
    options: StudentLessonListOptions = {},
  ): Promise<StudentLessonListResponse> {
    const parsedCourseId = publicIdSchema.parse(courseId)
    const parameters = new URLSearchParams()
    if (options.groupId !== undefined) {
      parameters.set('group', publicIdSchema.parse(options.groupId))
    }
    if (options.cursor !== undefined) {
      parameters.set('cursor', lessonCursorSchema.parse(options.cursor))
    }
    const query = parameters.size === 0 ? '' : `?${parameters.toString()}`
    return this.#request(
      `/courses/${encodeURIComponent(parsedCourseId)}/lessons${query}`,
      options,
      studentLessonListResponseSchema,
    )
  }

  async lesson(
    courseId: string,
    groupLessonId: string,
    options: CourseRequestOptions = {},
  ): Promise<StudentLessonSummary> {
    const parsedCourseId = publicIdSchema.parse(courseId)
    const parsedLessonId = publicIdSchema.parse(groupLessonId)
    return this.#request(
      `/courses/${encodeURIComponent(parsedCourseId)}/lessons/${encodeURIComponent(parsedLessonId)}`,
      options,
      studentLessonSummarySchema,
    )
  }

  async #request<T>(
    path: string,
    options: CourseRequestOptions,
    parser: ResponseParser<T>,
  ): Promise<T> {
    let response = await this.#send(path, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, options)
    }
    if (!response.ok) throw await this.#responseError(response)

    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new CourseProtocolError('Course API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new CourseProtocolError('Course API response failed contract validation', {
        cause: error,
        status: response.status,
      })
    }
  }

  async #send(path: string, options: CourseRequestOptions): Promise<Response> {
    try {
      return await this.#fetch(`${this.runtime.apiBase}${path}`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new CourseNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new CourseProtocolError('Course API returned an invalid error envelope', {
        cause: error,
        status: response.status,
      })
    }
  }
}

export function createStudentCourseClient(
  runtime: RuntimeConfig,
  options: StudentCourseClientOptions = {},
): StudentCourseClient {
  return new BrowserStudentCourseClient(runtime, options)
}

export function useStudentCoursesQuery(
  client: Pick<StudentCourseClient, 'list'>,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: courseQueryKeys.list(principal),
    queryFn: ({ signal }) => client.list({ signal }),
  })
}

export function useStudentHomeQuery(
  client: Pick<StudentCourseClient, 'home'>,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: courseQueryKeys.home(principal),
    queryFn: ({ signal }) => client.home({ signal }),
  })
}

export function useStudentCourseEnrollmentQuery(
  client: Pick<StudentCourseClient, 'enrollment'>,
  principal: PrincipalQueryScope,
  courseId: string,
) {
  return useQuery({
    queryKey: courseQueryKeys.enrollment(principal, courseId),
    queryFn: ({ signal }) => client.enrollment(courseId, { signal }),
  })
}

export function useStudentLessonsQuery(
  client: Pick<StudentCourseClient, 'lessons'>,
  principal: PrincipalQueryScope,
  courseId: string,
  groupId: string,
  cursor: LessonCursor | null = null,
) {
  return useQuery({
    queryKey: courseQueryKeys.lessons(principal, courseId, groupId, cursor),
    queryFn: ({ signal }) =>
      client.lessons(courseId, {
        groupId,
        ...(cursor === null ? {} : { cursor }),
        signal,
      }),
  })
}

export function useStudentLessonQuery(
  client: Pick<StudentCourseClient, 'lesson'>,
  principal: PrincipalQueryScope,
  courseId: string,
  groupId: string,
  groupLessonId: string,
) {
  return useQuery({
    queryKey: courseQueryKeys.lesson(principal, courseId, groupId, groupLessonId),
    queryFn: ({ signal }) => client.lesson(courseId, groupLessonId, { signal }),
  })
}

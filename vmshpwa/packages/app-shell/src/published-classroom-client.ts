import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  classroomQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  publishedClassroomAssignmentListResponseSchema,
  type PrincipalQueryScope,
  type PublishedClassroomAssignmentListResponse,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface PublishedClassroomRequestOptions {
  signal?: AbortSignal
}

export interface PublishedClassroomClient {
  list(
    options?: PublishedClassroomRequestOptions,
  ): Promise<PublishedClassroomAssignmentListResponse>
}

export interface PublishedClassroomClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export class PublishedClassroomProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'PublishedClassroomProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class PublishedClassroomNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Classroom assignment request could not reach the server', { cause: options.cause })
    this.name = 'PublishedClassroomNetworkError'
  }
}

function createClient(
  runtime: RuntimeConfig,
  audience: 'student' | 'family',
  path: string,
  options: PublishedClassroomClientOptions,
): PublishedClassroomClient {
  const configured = parseRuntimeConfigForAudience(audience, runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function send(signal?: AbortSignal): Promise<Response> {
    try {
      return await fetchImplementation(`${configured.apiBase}${path}`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
        ...(signal === undefined ? {} : { signal }),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new PublishedClassroomNetworkError({ cause: error })
    }
  }

  return {
    async list(
      request: PublishedClassroomRequestOptions = {},
    ): Promise<PublishedClassroomAssignmentListResponse> {
      let response = await send(request.signal)
      if (response.status === 401 && options.refreshSession) {
        await response.body?.cancel()
        await options.refreshSession()
        response = await send(request.signal)
      }
      if (!response.ok) {
        try {
          throw new ApiResponseError(response.status, apiErrorSchema.parse(await response.json()))
        } catch (error) {
          if (error instanceof ApiResponseError) throw error
          throw new PublishedClassroomProtocolError(
            'Classroom assignment API returned an invalid error envelope',
            { cause: error, status: response.status },
          )
        }
      }
      try {
        return publishedClassroomAssignmentListResponseSchema.parse(await response.json())
      } catch (error) {
        throw new PublishedClassroomProtocolError(
          'Classroom assignment API response failed contract validation',
          { cause: error, status: response.status },
        )
      }
    },
  }
}

export function createStudentClassroomAssignmentClient(
  runtime: RuntimeConfig,
  options: PublishedClassroomClientOptions = {},
): PublishedClassroomClient {
  return createClient(runtime, 'student', '/classroom-assignments', options)
}

export function createFamilyClassroomAssignmentClient(
  runtime: RuntimeConfig,
  studentPublicId: string,
  options: PublishedClassroomClientOptions = {},
): PublishedClassroomClient {
  const studentId = publicIdSchema.parse(studentPublicId)
  return createClient(
    runtime,
    'family',
    `/children/${encodeURIComponent(studentId)}/classroom-assignments`,
    options,
  )
}

export function usePublishedClassroomAssignmentsQuery(
  client: PublishedClassroomClient,
  principal: PrincipalQueryScope,
  studentPublicId?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: classroomQueryKeys.publishedAssignments(principal, studentPublicId),
    queryFn: ({ signal }) => client.list({ signal }),
    enabled,
  })
}

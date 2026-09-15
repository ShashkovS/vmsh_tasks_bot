import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  familyWrittenThreadResponseSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  writtenSubmissionQueryKeys,
  type FamilyWrittenThreadResponse,
  type PrincipalQueryScope,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface FamilyWrittenThreadRequestOptions {
  signal?: AbortSignal
}

export interface FamilyWrittenThreadClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface FamilyWrittenThreadClient {
  readonly runtime: RuntimeConfig
  thread(
    studentId: string,
    problemId: string,
    options?: FamilyWrittenThreadRequestOptions,
  ): Promise<FamilyWrittenThreadResponse>
}

export class FamilyWrittenThreadProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'FamilyWrittenThreadProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class FamilyWrittenThreadNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Family written-thread request could not reach the server', { cause: options.cause })
    this.name = 'FamilyWrittenThreadNetworkError'
  }
}

class BrowserFamilyWrittenThreadClient implements FamilyWrittenThreadClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: FamilyWrittenThreadClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('family', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async thread(
    studentId: string,
    problemId: string,
    options: FamilyWrittenThreadRequestOptions = {},
  ): Promise<FamilyWrittenThreadResponse> {
    const parsedStudentId = publicIdSchema.parse(studentId)
    const parsedProblemId = publicIdSchema.parse(problemId)
    const path = `/children/${encodeURIComponent(parsedStudentId)}/problems/${encodeURIComponent(parsedProblemId)}/thread`
    let response = await this.#send(path, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new FamilyWrittenThreadProtocolError(
        `Family written-thread API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }
    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new FamilyWrittenThreadProtocolError(
        'Family written-thread API returned malformed JSON',
        { cause: error, status: response.status },
      )
    }
    try {
      return familyWrittenThreadResponseSchema.parse(payload)
    } catch (error) {
      throw new FamilyWrittenThreadProtocolError(
        'Family written-thread API response failed contract validation',
        { cause: error, status: response.status },
      )
    }
  }

  async #send(path: string, options: FamilyWrittenThreadRequestOptions): Promise<Response> {
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
      throw new FamilyWrittenThreadNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new FamilyWrittenThreadProtocolError(
        'Family written-thread API returned an invalid error envelope',
        { cause: error, status: response.status },
      )
    }
  }
}

export function createFamilyWrittenThreadClient(
  runtime: RuntimeConfig,
  options: FamilyWrittenThreadClientOptions = {},
): FamilyWrittenThreadClient {
  return new BrowserFamilyWrittenThreadClient(runtime, options)
}

export function useFamilyWrittenThreadQuery(
  client: Pick<FamilyWrittenThreadClient, 'thread'>,
  principal: PrincipalQueryScope,
  studentId: string,
  problemId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: writtenSubmissionQueryKeys.familyThread(principal, studentId, problemId),
    queryFn: ({ signal }) => client.thread(studentId, problemId, { signal }),
    ...(options.enabled === undefined ? {} : { enabled: options.enabled }),
  })
}

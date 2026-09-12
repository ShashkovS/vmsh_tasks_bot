import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  recheckTestAttemptsRequestSchema,
  testAttemptRecheckPreviewResponseSchema,
  testAttemptRecheckResponseSchema,
  testSubmissionQueryKeys,
  type PrincipalQueryScope,
  type RecheckTestAttemptsRequest,
  type RuntimeConfig,
  type TestAttemptRecheckPreviewResponse,
  type TestAttemptRecheckResponse,
} from '@vmsh/contracts'

/**
 * Staff transport for the Phase-4 repair workflow. The preview binds an admin
 * action to the currently published problem revision so a stale tab cannot
 * silently recheck attempts against a different checker. See
 * `dev/development-plan/08-phase-4-test-submissions.md`.
 */

export interface TestAttemptRecheckRequestOptions {
  signal?: AbortSignal
}

export interface TestAttemptRecheckClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface TestAttemptRecheckClient {
  readonly runtime: RuntimeConfig
  preview(
    problemId: string,
    options?: TestAttemptRecheckRequestOptions,
  ): Promise<TestAttemptRecheckPreviewResponse>
  recheck(
    problemId: string,
    request: RecheckTestAttemptsRequest,
    options?: TestAttemptRecheckRequestOptions,
  ): Promise<TestAttemptRecheckResponse>
}

export class TestAttemptRecheckProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'TestAttemptRecheckProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class TestAttemptRecheckNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Test-attempt recheck request could not reach the server', { cause: options.cause })
    this.name = 'TestAttemptRecheckNetworkError'
  }
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

class BrowserTestAttemptRecheckClient implements TestAttemptRecheckClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: TestAttemptRecheckClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('staff', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async preview(
    problemId: string,
    options: TestAttemptRecheckRequestOptions = {},
  ): Promise<TestAttemptRecheckPreviewResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    return this.#request(
      parsedProblemId,
      { method: 'GET' },
      options,
      testAttemptRecheckPreviewResponseSchema,
    )
  }

  async recheck(
    problemId: string,
    request: RecheckTestAttemptsRequest,
    options: TestAttemptRecheckRequestOptions = {},
  ): Promise<TestAttemptRecheckResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    const parsedRequest = recheckTestAttemptsRequestSchema.parse(request)
    return this.#request(
      parsedProblemId,
      { method: 'POST', body: JSON.stringify(parsedRequest) },
      options,
      testAttemptRecheckResponseSchema,
    )
  }

  async #request<T>(
    problemId: string,
    input: { method: 'GET' | 'POST'; body?: string },
    options: TestAttemptRecheckRequestOptions,
    parser: ResponseParser<T>,
  ): Promise<T> {
    const path = `/problems/${encodeURIComponent(problemId)}/recheck-test-attempts`
    let response = await this.#send(path, input, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, input, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new TestAttemptRecheckProtocolError(
        `Test-attempt recheck API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }

    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new TestAttemptRecheckProtocolError(
        'Test-attempt recheck API returned malformed JSON',
        {
          cause: error,
          status: response.status,
        },
      )
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new TestAttemptRecheckProtocolError(
        'Test-attempt recheck API response failed contract validation',
        { cause: error, status: response.status },
      )
    }
  }

  async #send(
    path: string,
    input: { method: 'GET' | 'POST'; body?: string },
    options: TestAttemptRecheckRequestOptions,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (input.method === 'POST') headers['Content-Type'] = 'application/json'
    try {
      return await this.#fetch(`${this.runtime.apiBase}${path}`, {
        method: input.method,
        cache: 'no-store',
        credentials: 'include',
        headers,
        redirect: 'error',
        ...(input.body === undefined ? {} : { body: input.body }),
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new TestAttemptRecheckNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new TestAttemptRecheckProtocolError(
        'Test-attempt recheck API returned an invalid error envelope',
        { cause: error, status: response.status },
      )
    }
  }
}

export function createTestAttemptRecheckClient(
  runtime: RuntimeConfig,
  options: TestAttemptRecheckClientOptions = {},
): TestAttemptRecheckClient {
  return new BrowserTestAttemptRecheckClient(runtime, options)
}

export function useTestAttemptRecheckPreviewQuery(
  client: Pick<TestAttemptRecheckClient, 'preview'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  return useQuery({
    queryKey: testSubmissionQueryKeys.recheck(principal, problemId),
    queryFn: ({ signal }) => client.preview(problemId, { signal }),
  })
}

export function useTestAttemptRecheckMutation(
  client: Pick<TestAttemptRecheckClient, 'recheck'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...testSubmissionQueryKeys.recheck(principal, problemId), 'apply'],
    mutationFn: (request: RecheckTestAttemptsRequest) => client.recheck(problemId, request),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: testSubmissionQueryKeys.recheck(principal, problemId),
      })
    },
  })
}

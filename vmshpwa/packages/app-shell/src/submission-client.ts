import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  submitTestAnswerRequestSchema,
  submitTestAnswerResponseSchema,
  testAnswerInputResponseSchema,
  testAttemptCursorSchema,
  testAttemptHistoryResponseSchema,
  testSubmissionQueryKeys,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type SubmitTestAnswerRequest,
  type SubmitTestAnswerResponse,
  type TestAnswerInputResponse,
  type TestAttemptCursor,
  type TestAttemptHistoryResponse,
} from '@vmsh/contracts'

/**
 * Same-origin Student transport for Phase-4 test attempts. A 401 retry reuses
 * the exact request object and idempotency UUID. Offline persistence belongs
 * to `@vmsh/offline`, not this network adapter.
 */

export interface TestSubmissionRequestOptions {
  signal?: AbortSignal
}

export interface TestAttemptHistoryOptions extends TestSubmissionRequestOptions {
  cursor?: TestAttemptCursor
}

export interface TestSubmissionClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface TestSubmissionClient {
  readonly runtime: RuntimeConfig
  input(problemId: string, options?: TestSubmissionRequestOptions): Promise<TestAnswerInputResponse>
  submit(
    problemId: string,
    request: SubmitTestAnswerRequest,
    options?: TestSubmissionRequestOptions,
  ): Promise<SubmitTestAnswerResponse>
  history(
    problemId: string,
    options?: TestAttemptHistoryOptions,
  ): Promise<TestAttemptHistoryResponse>
}

export class TestSubmissionProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'TestSubmissionProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class TestSubmissionNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Test-submission request could not reach the server', { cause: options.cause })
    this.name = 'TestSubmissionNetworkError'
  }
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

class BrowserTestSubmissionClient implements TestSubmissionClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: TestSubmissionClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('student', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async input(
    problemId: string,
    options: TestSubmissionRequestOptions = {},
  ): Promise<TestAnswerInputResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    return this.#request(
      `/problems/${encodeURIComponent(parsedProblemId)}/test-input`,
      { method: 'GET' },
      options,
      200,
      testAnswerInputResponseSchema,
    )
  }

  async submit(
    problemId: string,
    request: SubmitTestAnswerRequest,
    options: TestSubmissionRequestOptions = {},
  ): Promise<SubmitTestAnswerResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    const parsedRequest = submitTestAnswerRequestSchema.parse(request)
    const body = JSON.stringify(parsedRequest)
    return this.#request(
      `/problems/${encodeURIComponent(parsedProblemId)}/test-attempts`,
      { method: 'POST', body },
      options,
      201,
      submitTestAnswerResponseSchema,
    )
  }

  async history(
    problemId: string,
    options: TestAttemptHistoryOptions = {},
  ): Promise<TestAttemptHistoryResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    const parameters = new URLSearchParams()
    if (options.cursor !== undefined) {
      parameters.set('cursor', testAttemptCursorSchema.parse(options.cursor))
    }
    const query = parameters.size === 0 ? '' : `?${parameters.toString()}`
    return this.#request(
      `/problems/${encodeURIComponent(parsedProblemId)}/test-attempts${query}`,
      { method: 'GET' },
      options,
      200,
      testAttemptHistoryResponseSchema,
    )
  }

  async #request<T>(
    path: string,
    input: { method: 'GET' | 'POST'; body?: string },
    options: TestSubmissionRequestOptions,
    expectedStatus: number,
    parser: ResponseParser<T>,
  ): Promise<T> {
    let response = await this.#send(path, input, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, input, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== expectedStatus) {
      await response.body?.cancel()
      throw new TestSubmissionProtocolError(
        `Test-submission API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }

    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new TestSubmissionProtocolError('Test-submission API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new TestSubmissionProtocolError(
        'Test-submission API response failed contract validation',
        { cause: error, status: response.status },
      )
    }
  }

  async #send(
    path: string,
    input: { method: 'GET' | 'POST'; body?: string },
    options: TestSubmissionRequestOptions,
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
      throw new TestSubmissionNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new TestSubmissionProtocolError(
        'Test-submission API returned an invalid error envelope',
        { cause: error, status: response.status },
      )
    }
  }
}

export function createTestSubmissionClient(
  runtime: RuntimeConfig,
  options: TestSubmissionClientOptions = {},
): TestSubmissionClient {
  return new BrowserTestSubmissionClient(runtime, options)
}

export function useTestAttemptHistoryQuery(
  client: Pick<TestSubmissionClient, 'history'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  return useInfiniteQuery({
    queryKey: testSubmissionQueryKeys.problem(principal, problemId),
    initialPageParam: null as TestAttemptCursor | null,
    queryFn: ({ pageParam, signal }) =>
      client.history(problemId, {
        ...(pageParam === null ? {} : { cursor: pageParam }),
        signal,
      }),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  })
}

export function useTestAnswerInputQuery(
  client: Pick<TestSubmissionClient, 'input'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  return useQuery({
    queryKey: testSubmissionQueryKeys.input(principal, problemId),
    queryFn: ({ signal }) => client.input(problemId, { signal }),
  })
}

export function useSubmitTestAnswerMutation(
  client: Pick<TestSubmissionClient, 'submit'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...testSubmissionQueryKeys.problem(principal, problemId), 'submit'],
    mutationFn: (request: SubmitTestAnswerRequest) => client.submit(problemId, request),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: testSubmissionQueryKeys.problem(principal, problemId),
      })
    },
  })
}

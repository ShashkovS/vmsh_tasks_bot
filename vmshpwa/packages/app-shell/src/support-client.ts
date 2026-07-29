import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  appendSupportEntryRequestSchema,
  createSupportThreadRequestSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  runtimeConfigSchema,
  supportQueryKeys,
  supportThreadResponseSchema,
  type AppendSupportEntryRequest,
  type CreateSupportThreadRequest,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type SupportThreadResponse,
} from '@vmsh/contracts'

export interface SupportRequestOptions {
  signal?: AbortSignal
}

export interface SupportClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface SupportClient {
  readonly runtime: RuntimeConfig
  create(
    request: CreateSupportThreadRequest,
    options?: SupportRequestOptions,
  ): Promise<SupportThreadResponse>
  get(threadId: string, options?: SupportRequestOptions): Promise<SupportThreadResponse>
  append(
    threadId: string,
    request: AppendSupportEntryRequest,
    options?: SupportRequestOptions,
  ): Promise<SupportThreadResponse>
}

export class SupportProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'SupportProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class SupportNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Support request could not reach the server', { cause: options.cause })
    this.name = 'SupportNetworkError'
  }
}

class BrowserSupportClient implements SupportClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: SupportClientOptions) {
    const parsed = runtimeConfigSchema.parse(runtime)
    if (parsed.audience === 'family') {
      throw new TypeError('Family does not participate in private support threads')
    }
    this.runtime = parseRuntimeConfigForAudience(parsed.audience, parsed)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async create(
    request: CreateSupportThreadRequest,
    options: SupportRequestOptions = {},
  ): Promise<SupportThreadResponse> {
    if (this.runtime.audience !== 'student') {
      throw new TypeError('Only Student can create a support thread')
    }
    return this.#jsonRequest(
      '/questions',
      'POST',
      JSON.stringify(createSupportThreadRequestSchema.parse(request)),
      options,
    )
  }

  async get(threadId: string, options: SupportRequestOptions = {}): Promise<SupportThreadResponse> {
    const parsedThreadId = publicIdSchema.parse(threadId)
    return this.#jsonRequest(
      `/questions/${encodeURIComponent(parsedThreadId)}`,
      'GET',
      undefined,
      options,
    )
  }

  async append(
    threadId: string,
    request: AppendSupportEntryRequest,
    options: SupportRequestOptions = {},
  ): Promise<SupportThreadResponse> {
    const parsedThreadId = publicIdSchema.parse(threadId)
    return this.#jsonRequest(
      `/questions/${encodeURIComponent(parsedThreadId)}/entries`,
      'POST',
      JSON.stringify(appendSupportEntryRequestSchema.parse(request)),
      options,
    )
  }

  async #jsonRequest(
    path: string,
    method: 'GET' | 'POST',
    body: string | undefined,
    options: SupportRequestOptions,
  ): Promise<SupportThreadResponse> {
    let response = await this.#send(path, method, body, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, method, body, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new SupportProtocolError(`Support API returned unexpected HTTP ${response.status}`, {
        status: response.status,
      })
    }
    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new SupportProtocolError('Support API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return supportThreadResponseSchema.parse(payload)
    } catch (error) {
      throw new SupportProtocolError('Support API response failed contract validation', {
        cause: error,
        status: response.status,
      })
    }
  }

  async #send(
    path: string,
    method: 'GET' | 'POST',
    body: string | undefined,
    options: SupportRequestOptions,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (method === 'POST') headers['Content-Type'] = 'application/json'
    try {
      return await this.#fetch(`${this.runtime.apiBase}${path}`, {
        method,
        cache: 'no-store',
        credentials: 'include',
        headers,
        redirect: 'error',
        ...(body === undefined ? {} : { body }),
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new SupportNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new SupportProtocolError('Support API returned an invalid error envelope', {
        cause: error,
        status: response.status,
      })
    }
  }
}

export function createSupportClient(
  runtime: RuntimeConfig,
  options: SupportClientOptions = {},
): SupportClient {
  return new BrowserSupportClient(runtime, options)
}

export function useSupportThreadQuery(
  client: Pick<SupportClient, 'get'>,
  principal: PrincipalQueryScope,
  threadId: string,
) {
  return useQuery({
    queryKey: supportQueryKeys.thread(principal, threadId),
    queryFn: ({ signal }) => client.get(threadId, { signal }),
    meta: { realtimeResources: [`questions/${threadId}`] },
  })
}

export function useCreateSupportThreadMutation(
  client: Pick<SupportClient, 'create'>,
  principal: PrincipalQueryScope,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...supportQueryKeys.all(principal), 'create'],
    mutationFn: (request: CreateSupportThreadRequest) => client.create(request),
    onSuccess: (response) => {
      queryClient.setQueryData(
        supportQueryKeys.thread(principal, response.thread.threadId),
        response,
      )
    },
  })
}

export function useAppendSupportEntryMutation(
  client: Pick<SupportClient, 'append'>,
  principal: PrincipalQueryScope,
  threadId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...supportQueryKeys.thread(principal, threadId), 'append'],
    mutationFn: (request: AppendSupportEntryRequest) => client.append(threadId, request),
    onSuccess: (response) => {
      queryClient.setQueryData(supportQueryKeys.thread(principal, threadId), response)
    },
  })
}

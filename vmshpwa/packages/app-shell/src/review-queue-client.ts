import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  claimReviewItemRequestSchema,
  completeReviewRequestSchema,
  completeReviewResponseSchema,
  deleteReviewInternalReactionRequestSchema,
  mutateReviewLeaseRequestSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  releaseReviewLeaseResponseSchema,
  reviewLeaseResponseSchema,
  reviewInternalReactionResponseSchema,
  reviewQueueListQuerySchema,
  reviewQueueListResponseSchema,
  reviewQueueQueryKeys,
  setReviewInternalReactionRequestSchema,
  type CompleteReviewRequest,
  type CompleteReviewResponse,
  type PrincipalQueryScope,
  type ReviewInternalReactionResponse,
  type ReviewLeaseResponse,
  type ReviewQueueListQuery,
  type ReviewQueueListResponse,
  type RuntimeConfig,
  type WrittenTeacherReactionId,
} from '@vmsh/contracts'

/** Staff transport for the Phase-6 scoped, synonym-aware review queue. */

export interface ReviewQueueRequestOptions {
  signal?: AbortSignal
}

export interface ReviewQueueClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface ReviewQueueClient {
  readonly runtime: RuntimeConfig
  list(
    query?: ReviewQueueListQuery,
    options?: ReviewQueueRequestOptions,
  ): Promise<ReviewQueueListResponse>
  claim(queueId: string, options?: ReviewQueueRequestOptions): Promise<ReviewLeaseResponse>
  heartbeat(
    queueId: string,
    claimToken: string,
    options?: ReviewQueueRequestOptions,
  ): Promise<ReviewLeaseResponse>
  release(queueId: string, claimToken: string, options?: ReviewQueueRequestOptions): Promise<number>
  complete(
    queueId: string,
    request: CompleteReviewRequest,
    options?: ReviewQueueRequestOptions,
  ): Promise<CompleteReviewResponse>
  setInternalReaction(
    reviewId: string,
    reactionId: WrittenTeacherReactionId,
    expectedVersion: number,
    options?: ReviewQueueRequestOptions,
  ): Promise<ReviewInternalReactionResponse>
  deleteInternalReaction(
    reviewId: string,
    expectedVersion: number,
    options?: ReviewQueueRequestOptions,
  ): Promise<ReviewInternalReactionResponse>
}

export class ReviewQueueProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'ReviewQueueProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class ReviewQueueNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Review queue request could not reach the server', { cause: options.cause })
    this.name = 'ReviewQueueNetworkError'
  }
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

class BrowserReviewQueueClient implements ReviewQueueClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: ReviewQueueClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('staff', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async list(
    query: ReviewQueueListQuery = {},
    options: ReviewQueueRequestOptions = {},
  ): Promise<ReviewQueueListResponse> {
    const parsed = reviewQueueListQuerySchema.parse(query)
    const search = new URLSearchParams()
    if (parsed.problemGroup) search.set('problemGroup', parsed.problemGroup)
    if (parsed.sort !== 'oldest') search.set('sort', parsed.sort)
    if (parsed.cursor) search.set('cursor', parsed.cursor)
    const suffix = search.size === 0 ? '' : `?${search.toString()}`
    return this.#jsonRequest(
      `/review/items${suffix}`,
      'GET',
      undefined,
      options,
      reviewQueueListResponseSchema,
    )
  }

  async claim(
    queueId: string,
    options: ReviewQueueRequestOptions = {},
  ): Promise<ReviewLeaseResponse> {
    const parsedQueueId = publicIdSchema.parse(queueId)
    const body = JSON.stringify(claimReviewItemRequestSchema.parse({ schemaVersion: 1 }))
    return this.#jsonRequest(
      `/review/items/${encodeURIComponent(parsedQueueId)}/claim`,
      'POST',
      body,
      options,
      reviewLeaseResponseSchema,
    )
  }

  async heartbeat(
    queueId: string,
    claimToken: string,
    options: ReviewQueueRequestOptions = {},
  ): Promise<ReviewLeaseResponse> {
    return this.#leaseMutation(queueId, claimToken, 'heartbeat', options)
  }

  async release(
    queueId: string,
    claimToken: string,
    options: ReviewQueueRequestOptions = {},
  ): Promise<number> {
    const response = await this.#leaseMutationRequest(
      queueId,
      claimToken,
      'release',
      options,
      releaseReviewLeaseResponseSchema,
    )
    return response.releasedItems
  }

  async complete(
    queueId: string,
    request: CompleteReviewRequest,
    options: ReviewQueueRequestOptions = {},
  ): Promise<CompleteReviewResponse> {
    const parsedQueueId = publicIdSchema.parse(queueId)
    const body = JSON.stringify(completeReviewRequestSchema.parse(request))
    return this.#jsonRequest(
      `/review/items/${encodeURIComponent(parsedQueueId)}/complete`,
      'POST',
      body,
      options,
      completeReviewResponseSchema,
    )
  }

  async setInternalReaction(
    reviewId: string,
    reactionId: WrittenTeacherReactionId,
    expectedVersion: number,
    options: ReviewQueueRequestOptions = {},
  ): Promise<ReviewInternalReactionResponse> {
    const parsedReviewId = publicIdSchema.parse(reviewId)
    const body = JSON.stringify(
      setReviewInternalReactionRequestSchema.parse({
        schemaVersion: 1,
        reactionId,
        expectedVersion,
      }),
    )
    return this.#jsonRequest(
      `/reviews/${encodeURIComponent(parsedReviewId)}/internal-reaction`,
      'PUT',
      body,
      options,
      reviewInternalReactionResponseSchema,
    )
  }

  async deleteInternalReaction(
    reviewId: string,
    expectedVersion: number,
    options: ReviewQueueRequestOptions = {},
  ): Promise<ReviewInternalReactionResponse> {
    const parsedReviewId = publicIdSchema.parse(reviewId)
    const body = JSON.stringify(
      deleteReviewInternalReactionRequestSchema.parse({
        schemaVersion: 1,
        expectedVersion,
      }),
    )
    return this.#jsonRequest(
      `/reviews/${encodeURIComponent(parsedReviewId)}/internal-reaction`,
      'DELETE',
      body,
      options,
      reviewInternalReactionResponseSchema,
    )
  }

  async #leaseMutation(
    queueId: string,
    claimToken: string,
    action: 'heartbeat',
    options: ReviewQueueRequestOptions,
  ): Promise<ReviewLeaseResponse> {
    return this.#leaseMutationRequest(
      queueId,
      claimToken,
      action,
      options,
      reviewLeaseResponseSchema,
    )
  }

  async #leaseMutationRequest<T>(
    queueId: string,
    claimToken: string,
    action: 'heartbeat' | 'release',
    options: ReviewQueueRequestOptions,
    parser: ResponseParser<T>,
  ): Promise<T> {
    const parsedQueueId = publicIdSchema.parse(queueId)
    const body = JSON.stringify(
      mutateReviewLeaseRequestSchema.parse({ schemaVersion: 1, claimToken }),
    )
    return this.#jsonRequest(
      `/review/items/${encodeURIComponent(parsedQueueId)}/${action}`,
      'POST',
      body,
      options,
      parser,
    )
  }

  async #jsonRequest<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body: string | undefined,
    options: ReviewQueueRequestOptions,
    parser: ResponseParser<T>,
  ): Promise<T> {
    let response = await this.#send(path, method, body, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, method, body, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new ReviewQueueProtocolError(
        `Review queue API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }
    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new ReviewQueueProtocolError('Review queue API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new ReviewQueueProtocolError('Review queue API response failed contract validation', {
        cause: error,
        status: response.status,
      })
    }
  }

  async #send(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body: string | undefined,
    options: ReviewQueueRequestOptions,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (method !== 'GET') headers['Content-Type'] = 'application/json'
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
      throw new ReviewQueueNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new ReviewQueueProtocolError('Review queue API returned an invalid error envelope', {
        cause: error,
        status: response.status,
      })
    }
  }
}

export function createReviewQueueClient(
  runtime: RuntimeConfig,
  options: ReviewQueueClientOptions = {},
): ReviewQueueClient {
  return new BrowserReviewQueueClient(runtime, options)
}

export function useReviewQueueQuery(
  client: Pick<ReviewQueueClient, 'list'>,
  principal: PrincipalQueryScope,
  query: ReviewQueueListQuery = {},
) {
  return useQuery({
    queryKey: reviewQueueQueryKeys.list(principal, query),
    queryFn: ({ signal }) => client.list(query, { signal }),
  })
}

export function useClaimReviewItemMutation(
  client: Pick<ReviewQueueClient, 'claim'>,
  principal: PrincipalQueryScope,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...reviewQueueQueryKeys.list(principal), 'claim'],
    mutationFn: (queueId: string) => client.claim(queueId),
    onSuccess: async (response, queueId) => {
      queryClient.setQueryData(reviewQueueQueryKeys.lease(principal, queueId), response)
      await queryClient.invalidateQueries({
        queryKey: reviewQueueQueryKeys.all(principal),
      })
    },
  })
}

export function useHeartbeatReviewLeaseMutation(
  client: Pick<ReviewQueueClient, 'heartbeat'>,
  principal: PrincipalQueryScope,
  queueId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...reviewQueueQueryKeys.lease(principal, queueId), 'heartbeat'],
    mutationFn: (claimToken: string) => client.heartbeat(queueId, claimToken),
    onSuccess: (response) => {
      queryClient.setQueryData(reviewQueueQueryKeys.lease(principal, queueId), response)
    },
  })
}

export function useReleaseReviewLeaseMutation(
  client: Pick<ReviewQueueClient, 'release'>,
  principal: PrincipalQueryScope,
  queueId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...reviewQueueQueryKeys.lease(principal, queueId), 'release'],
    mutationFn: (claimToken: string) => client.release(queueId, claimToken),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: reviewQueueQueryKeys.lease(principal, queueId) })
      await queryClient.invalidateQueries({
        queryKey: reviewQueueQueryKeys.all(principal),
      })
    },
  })
}

export function useCompleteReviewMutation(
  client: Pick<ReviewQueueClient, 'complete'>,
  principal: PrincipalQueryScope,
  queueId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...reviewQueueQueryKeys.lease(principal, queueId), 'complete'],
    mutationFn: (request: CompleteReviewRequest) => client.complete(queueId, request),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: reviewQueueQueryKeys.lease(principal, queueId) })
      await queryClient.invalidateQueries({
        queryKey: reviewQueueQueryKeys.all(principal),
      })
    },
  })
}

export function useSetReviewInternalReactionMutation(
  client: Pick<ReviewQueueClient, 'setInternalReaction'>,
  principal: PrincipalQueryScope,
  reviewId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...reviewQueueQueryKeys.review(principal, reviewId), 'internal-reaction', 'set'],
    mutationFn: ({
      reactionId,
      expectedVersion,
    }: {
      reactionId: WrittenTeacherReactionId
      expectedVersion: number
    }) => client.setInternalReaction(reviewId, reactionId, expectedVersion),
    onSuccess: (response) => {
      queryClient.setQueryData(reviewQueueQueryKeys.review(principal, reviewId), response)
    },
  })
}

export function useDeleteReviewInternalReactionMutation(
  client: Pick<ReviewQueueClient, 'deleteInternalReaction'>,
  principal: PrincipalQueryScope,
  reviewId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [
      ...reviewQueueQueryKeys.review(principal, reviewId),
      'internal-reaction',
      'delete',
    ],
    mutationFn: (expectedVersion: number) =>
      client.deleteInternalReaction(reviewId, expectedVersion),
    onSuccess: (response) => {
      queryClient.setQueryData(reviewQueueQueryKeys.review(principal, reviewId), response)
    },
  })
}

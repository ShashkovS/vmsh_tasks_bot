import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  createWrittenAttachmentResponseSchema,
  createWrittenEntryRequestSchema,
  createWrittenEntryResponseSchema,
  deleteWrittenStudentReactionRequestSchema,
  deleteWrittenAttachmentRequestSchema,
  mutateWrittenAttachmentsResponseSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  reorderWrittenAttachmentsRequestSchema,
  replaceWrittenEntryRequestSchema,
  replaceWrittenEntryResponseSchema,
  setWrittenStudentReactionRequestSchema,
  submitWrittenEntryRequestSchema,
  submitWrittenEntryResponseSchema,
  writtenAttachmentUploadMetadataSchema,
  writtenSubmissionQueryKeys,
  writtenThreadResponseSchema,
  writtenStudentReactionResponseSchema,
  type CreateWrittenAttachmentResponse,
  type CreateWrittenEntryRequest,
  type CreateWrittenEntryResponse,
  type DeleteWrittenAttachmentRequest,
  type DeleteWrittenStudentReactionRequest,
  type MutateWrittenAttachmentsResponse,
  type PrincipalQueryScope,
  type ReorderWrittenAttachmentsRequest,
  type ReplaceWrittenEntryRequest,
  type ReplaceWrittenEntryResponse,
  type RuntimeConfig,
  type SetWrittenStudentReactionRequest,
  type SubmitWrittenEntryRequest,
  type SubmitWrittenEntryResponse,
  type WrittenAttachmentUploadMetadata,
  type WrittenThreadResponse,
  type WrittenStudentReactionResponse,
} from '@vmsh/contracts'
import { recordProductAction } from './product-analytics'

/**
 * Same-origin Student transport for Phase-5 written threads. All mutations
 * preserve caller-generated idempotency keys across the one allowed 401
 * refresh retry. Durable orchestration belongs to `@vmsh/offline`.
 */

export interface WrittenSubmissionRequestOptions {
  signal?: AbortSignal
}

export interface WrittenAttachmentUpload {
  metadata: WrittenAttachmentUploadMetadata
  asset: Blob
  fileName: string
}

export interface WrittenSubmissionClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface WrittenSubmissionClient {
  readonly runtime: RuntimeConfig
  thread(
    problemId: string,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<WrittenThreadResponse>
  create(
    problemId: string,
    request: CreateWrittenEntryRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<CreateWrittenEntryResponse>
  upload(
    entryId: string,
    upload: WrittenAttachmentUpload,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<CreateWrittenAttachmentResponse>
  attachmentMedia(
    entryId: string,
    attachmentId: string,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<Blob>
  reorder(
    entryId: string,
    request: ReorderWrittenAttachmentsRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<MutateWrittenAttachmentsResponse>
  deleteAttachment(
    entryId: string,
    attachmentId: string,
    request: DeleteWrittenAttachmentRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<MutateWrittenAttachmentsResponse>
  submit(
    entryId: string,
    request: SubmitWrittenEntryRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<SubmitWrittenEntryResponse>
  replace(
    entryId: string,
    request: ReplaceWrittenEntryRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<ReplaceWrittenEntryResponse>
  setStudentReaction(
    reviewId: string,
    request: SetWrittenStudentReactionRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<WrittenStudentReactionResponse>
  deleteStudentReaction(
    reviewId: string,
    request: DeleteWrittenStudentReactionRequest,
    options?: WrittenSubmissionRequestOptions,
  ): Promise<WrittenStudentReactionResponse>
}

export class WrittenSubmissionProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'WrittenSubmissionProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class WrittenSubmissionNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Written-submission request could not reach the server', { cause: options.cause })
    this.name = 'WrittenSubmissionNetworkError'
  }
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

interface WrittenRequest {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: BodyInit
  contentType?: string
  accept?: string
}

class BrowserWrittenSubmissionClient implements WrittenSubmissionClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: WrittenSubmissionClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('student', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async thread(
    problemId: string,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<WrittenThreadResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    return this.#request(
      `/problems/${encodeURIComponent(parsedProblemId)}/thread`,
      { method: 'GET' },
      options,
      200,
      writtenThreadResponseSchema,
    )
  }

  async create(
    problemId: string,
    request: CreateWrittenEntryRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<CreateWrittenEntryResponse> {
    const parsedProblemId = publicIdSchema.parse(problemId)
    const body = JSON.stringify(createWrittenEntryRequestSchema.parse(request))
    return this.#request(
      `/problems/${encodeURIComponent(parsedProblemId)}/thread/entries`,
      { method: 'POST', body, contentType: 'application/json' },
      options,
      201,
      createWrittenEntryResponseSchema,
    )
  }

  async upload(
    entryId: string,
    upload: WrittenAttachmentUpload,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<CreateWrittenAttachmentResponse> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const metadata = writtenAttachmentUploadMetadataSchema.parse(upload.metadata)
    const fileName = upload.fileName.trim()
    if (!fileName || fileName.length > 255) throw new TypeError('Attachment filename is invalid')
    if (upload.asset.size < 1) throw new TypeError('Attachment asset is empty')
    const body = new FormData()
    body.set('schemaVersion', String(metadata.schemaVersion))
    body.set('idempotencyKey', metadata.idempotencyKey)
    body.set('expectedEntryVersion', String(metadata.expectedEntryVersion))
    body.set('expectedThreadVersion', String(metadata.expectedThreadVersion))
    body.set('ordinal', String(metadata.ordinal))
    body.set('asset', upload.asset, fileName)
    const response = await this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/attachments`,
      { method: 'POST', body },
      options,
      201,
      createWrittenAttachmentResponseSchema,
    )
    recordProductAction('photo.attach', { type: 'submission', id: parsedEntryId })
    return response
  }

  async attachmentMedia(
    entryId: string,
    attachmentId: string,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<Blob> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const parsedAttachmentId = publicIdSchema.parse(attachmentId)
    const path = `/thread-entries/${encodeURIComponent(parsedEntryId)}/attachments/${encodeURIComponent(parsedAttachmentId)}/media`
    let response = await this.#send(path, { method: 'GET', accept: 'image/webp' }, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, { method: 'GET', accept: 'image/webp' }, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new WrittenSubmissionProtocolError(
        `Written attachment API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }
    const contentType = response.headers.get('Content-Type')?.split(';', 1)[0]?.trim()
    const blob = await response.blob()
    if (contentType !== 'image/webp' || blob.size < 1) {
      throw new WrittenSubmissionProtocolError('Written attachment API returned invalid media', {
        status: response.status,
      })
    }
    return blob.type === 'image/webp' ? blob : new Blob([blob], { type: 'image/webp' })
  }

  async reorder(
    entryId: string,
    request: ReorderWrittenAttachmentsRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<MutateWrittenAttachmentsResponse> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const body = JSON.stringify(reorderWrittenAttachmentsRequestSchema.parse(request))
    return this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/attachments/order`,
      { method: 'PATCH', body, contentType: 'application/json' },
      options,
      200,
      mutateWrittenAttachmentsResponseSchema,
    )
  }

  async deleteAttachment(
    entryId: string,
    attachmentId: string,
    request: DeleteWrittenAttachmentRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<MutateWrittenAttachmentsResponse> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const parsedAttachmentId = publicIdSchema.parse(attachmentId)
    const body = JSON.stringify(deleteWrittenAttachmentRequestSchema.parse(request))
    return this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/attachments/${encodeURIComponent(parsedAttachmentId)}`,
      { method: 'DELETE', body, contentType: 'application/json' },
      options,
      200,
      mutateWrittenAttachmentsResponseSchema,
    )
  }

  async submit(
    entryId: string,
    request: SubmitWrittenEntryRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<SubmitWrittenEntryResponse> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const body = JSON.stringify(submitWrittenEntryRequestSchema.parse(request))
    const response = await this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/submit`,
      { method: 'POST', body, contentType: 'application/json' },
      options,
      200,
      submitWrittenEntryResponseSchema,
    )
    recordProductAction('written.submit', { type: 'submission', id: parsedEntryId })
    return response
  }

  async replace(
    entryId: string,
    request: ReplaceWrittenEntryRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<ReplaceWrittenEntryResponse> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const body = JSON.stringify(replaceWrittenEntryRequestSchema.parse(request))
    return this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/replace`,
      { method: 'POST', body, contentType: 'application/json' },
      options,
      200,
      replaceWrittenEntryResponseSchema,
    )
  }

  async setStudentReaction(
    reviewId: string,
    request: SetWrittenStudentReactionRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<WrittenStudentReactionResponse> {
    const parsedReviewId = publicIdSchema.parse(reviewId)
    const body = JSON.stringify(setWrittenStudentReactionRequestSchema.parse(request))
    return this.#request(
      `/reviews/${encodeURIComponent(parsedReviewId)}/reaction`,
      { method: 'PUT', body, contentType: 'application/json' },
      options,
      200,
      writtenStudentReactionResponseSchema,
    )
  }

  async deleteStudentReaction(
    reviewId: string,
    request: DeleteWrittenStudentReactionRequest,
    options: WrittenSubmissionRequestOptions = {},
  ): Promise<WrittenStudentReactionResponse> {
    const parsedReviewId = publicIdSchema.parse(reviewId)
    const body = JSON.stringify(deleteWrittenStudentReactionRequestSchema.parse(request))
    return this.#request(
      `/reviews/${encodeURIComponent(parsedReviewId)}/reaction`,
      { method: 'DELETE', body, contentType: 'application/json' },
      options,
      200,
      writtenStudentReactionResponseSchema,
    )
  }

  async #request<T>(
    path: string,
    input: WrittenRequest,
    options: WrittenSubmissionRequestOptions,
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
      throw new WrittenSubmissionProtocolError(
        `Written-submission API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }

    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new WrittenSubmissionProtocolError('Written-submission API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new WrittenSubmissionProtocolError(
        'Written-submission API response failed contract validation',
        { cause: error, status: response.status },
      )
    }
  }

  async #send(
    path: string,
    input: WrittenRequest,
    options: WrittenSubmissionRequestOptions,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: input.accept ?? 'application/json' }
    if (input.contentType) headers['Content-Type'] = input.contentType
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
      throw new WrittenSubmissionNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new WrittenSubmissionProtocolError(
        'Written-submission API returned an invalid error envelope',
        { cause: error, status: response.status },
      )
    }
  }
}

export function createWrittenSubmissionClient(
  runtime: RuntimeConfig,
  options: WrittenSubmissionClientOptions = {},
): WrittenSubmissionClient {
  return new BrowserWrittenSubmissionClient(runtime, options)
}

export function useWrittenThreadQuery(
  client: Pick<WrittenSubmissionClient, 'thread'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  return useQuery({
    queryKey: writtenSubmissionQueryKeys.thread(principal, problemId),
    queryFn: ({ signal }) => client.thread(problemId, { signal }),
  })
}

export function useWrittenStudentReactionMutation(
  client: Pick<WrittenSubmissionClient, 'setStudentReaction' | 'deleteStudentReaction'>,
  principal: PrincipalQueryScope,
  problemId: string,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: [...writtenSubmissionQueryKeys.thread(principal, problemId), 'student-reaction'],
    mutationFn: ({
      reviewId,
      reactionId,
      expectedVersion,
    }: {
      reviewId: string
      reactionId: SetWrittenStudentReactionRequest['reactionId'] | null
      expectedVersion: number
    }) =>
      reactionId === null
        ? client.deleteStudentReaction(reviewId, { schemaVersion: 1, expectedVersion })
        : client.setStudentReaction(reviewId, {
            schemaVersion: 1,
            reactionId,
            expectedVersion,
          }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: writtenSubmissionQueryKeys.thread(principal, problemId),
      })
    },
  })
}

import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  createWrittenAttachmentResponseSchema,
  createWrittenEntryRequestSchema,
  createWrittenEntryResponseSchema,
  deleteWrittenAttachmentRequestSchema,
  mutateWrittenAttachmentsResponseSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  reorderWrittenAttachmentsRequestSchema,
  replaceWrittenEntryRequestSchema,
  replaceWrittenEntryResponseSchema,
  submitWrittenEntryRequestSchema,
  submitWrittenEntryResponseSchema,
  writtenAttachmentUploadMetadataSchema,
  writtenSubmissionQueryKeys,
  writtenThreadResponseSchema,
  type CreateWrittenAttachmentResponse,
  type CreateWrittenEntryRequest,
  type CreateWrittenEntryResponse,
  type DeleteWrittenAttachmentRequest,
  type MutateWrittenAttachmentsResponse,
  type PrincipalQueryScope,
  type ReorderWrittenAttachmentsRequest,
  type ReplaceWrittenEntryRequest,
  type ReplaceWrittenEntryResponse,
  type RuntimeConfig,
  type SubmitWrittenEntryRequest,
  type SubmitWrittenEntryResponse,
  type WrittenAttachmentUploadMetadata,
  type WrittenThreadResponse,
} from '@vmsh/contracts'

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
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: BodyInit
  contentType?: string
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
    return this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/attachments`,
      { method: 'POST', body },
      options,
      201,
      createWrittenAttachmentResponseSchema,
    )
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
    return this.#request(
      `/thread-entries/${encodeURIComponent(parsedEntryId)}/submit`,
      { method: 'POST', body, contentType: 'application/json' },
      options,
      200,
      submitWrittenEntryResponseSchema,
    )
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
    const headers: Record<string, string> = { Accept: 'application/json' }
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

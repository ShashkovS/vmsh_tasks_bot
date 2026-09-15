import { useMutation } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  previewWrittenMaterialReassignmentRequestSchema,
  previewWrittenMaterialReassignmentResponseSchema,
  publicIdSchema,
  reassignWrittenMaterialRequestSchema,
  reassignWrittenMaterialResponseSchema,
  type PreviewWrittenMaterialReassignmentRequest,
  type PreviewWrittenMaterialReassignmentResponse,
  type ReassignWrittenMaterialRequest,
  type ReassignWrittenMaterialResponse,
  type RuntimeConfig,
} from '@vmsh/contracts'

/**
 * Staff transport for the Phase-5 append-only correction flow. Preview and
 * commit use the same concrete item references; retries preserve the exact
 * caller-generated idempotency key. See development-plan Phase 5.
 */

export interface WrittenMaterialReassignmentRequestOptions {
  signal?: AbortSignal
}

export interface WrittenMaterialReassignmentClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface WrittenMaterialReassignmentClient {
  readonly runtime: RuntimeConfig
  preview(
    request: PreviewWrittenMaterialReassignmentRequest,
    options?: WrittenMaterialReassignmentRequestOptions,
  ): Promise<PreviewWrittenMaterialReassignmentResponse>
  reassign(
    request: ReassignWrittenMaterialRequest,
    options?: WrittenMaterialReassignmentRequestOptions,
  ): Promise<ReassignWrittenMaterialResponse>
  attachmentMedia(
    entryId: string,
    attachmentId: string,
    options?: WrittenMaterialReassignmentRequestOptions,
  ): Promise<Blob>
}

export class WrittenMaterialReassignmentProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'WrittenMaterialReassignmentProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class WrittenMaterialReassignmentNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Written-material reassignment request could not reach the server', {
      cause: options.cause,
    })
    this.name = 'WrittenMaterialReassignmentNetworkError'
  }
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

class BrowserWrittenMaterialReassignmentClient implements WrittenMaterialReassignmentClient {
  readonly runtime: RuntimeConfig

  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: WrittenMaterialReassignmentClientOptions) {
    this.runtime = parseRuntimeConfigForAudience('staff', runtime)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async preview(
    request: PreviewWrittenMaterialReassignmentRequest,
    options: WrittenMaterialReassignmentRequestOptions = {},
  ): Promise<PreviewWrittenMaterialReassignmentResponse> {
    const body = JSON.stringify(previewWrittenMaterialReassignmentRequestSchema.parse(request))
    return this.#jsonRequest(
      '/submission-material-reassignments/preview',
      body,
      options,
      previewWrittenMaterialReassignmentResponseSchema,
    )
  }

  async reassign(
    request: ReassignWrittenMaterialRequest,
    options: WrittenMaterialReassignmentRequestOptions = {},
  ): Promise<ReassignWrittenMaterialResponse> {
    const body = JSON.stringify(reassignWrittenMaterialRequestSchema.parse(request))
    return this.#jsonRequest(
      '/submission-material-reassignments',
      body,
      options,
      reassignWrittenMaterialResponseSchema,
    )
  }

  async attachmentMedia(
    entryId: string,
    attachmentId: string,
    options: WrittenMaterialReassignmentRequestOptions = {},
  ): Promise<Blob> {
    const parsedEntryId = publicIdSchema.parse(entryId)
    const parsedAttachmentId = publicIdSchema.parse(attachmentId)
    const path = `/thread-entries/${encodeURIComponent(parsedEntryId)}/attachments/${encodeURIComponent(parsedAttachmentId)}/media`
    let response = await this.#send(path, 'GET', undefined, 'image/webp', options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, 'GET', undefined, 'image/webp', options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new WrittenMaterialReassignmentProtocolError(
        `Written-material media API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }
    const contentType = response.headers.get('Content-Type')?.split(';', 1)[0]?.trim()
    const blob = await response.blob()
    if (contentType !== 'image/webp' || blob.size < 1) {
      throw new WrittenMaterialReassignmentProtocolError(
        'Written-material media API returned invalid media',
        { status: response.status },
      )
    }
    return blob.type === 'image/webp' ? blob : new Blob([blob], { type: 'image/webp' })
  }

  async #jsonRequest<T>(
    path: string,
    body: string,
    options: WrittenMaterialReassignmentRequestOptions,
    parser: ResponseParser<T>,
  ): Promise<T> {
    let response = await this.#send(path, 'POST', body, 'application/json', options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, 'POST', body, 'application/json', options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 200) {
      await response.body?.cancel()
      throw new WrittenMaterialReassignmentProtocolError(
        `Written-material reassignment API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }
    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new WrittenMaterialReassignmentProtocolError(
        'Written-material reassignment API returned malformed JSON',
        { cause: error, status: response.status },
      )
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new WrittenMaterialReassignmentProtocolError(
        'Written-material reassignment API response failed contract validation',
        { cause: error, status: response.status },
      )
    }
  }

  async #send(
    path: string,
    method: 'GET' | 'POST',
    body: string | undefined,
    accept: string,
    options: WrittenMaterialReassignmentRequestOptions,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: accept }
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
      throw new WrittenMaterialReassignmentNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new WrittenMaterialReassignmentProtocolError(
        'Written-material reassignment API returned an invalid error envelope',
        { cause: error, status: response.status },
      )
    }
  }
}

export function createWrittenMaterialReassignmentClient(
  runtime: RuntimeConfig,
  options: WrittenMaterialReassignmentClientOptions = {},
): WrittenMaterialReassignmentClient {
  return new BrowserWrittenMaterialReassignmentClient(runtime, options)
}

export function useWrittenMaterialReassignmentPreviewMutation(
  client: Pick<WrittenMaterialReassignmentClient, 'preview'>,
) {
  return useMutation({
    mutationKey: ['staff', 'written-material-reassignment', 'preview'],
    mutationFn: (request: PreviewWrittenMaterialReassignmentRequest) => client.preview(request),
  })
}

export function useWrittenMaterialReassignmentMutation(
  client: Pick<WrittenMaterialReassignmentClient, 'reassign'>,
) {
  return useMutation({
    mutationKey: ['staff', 'written-material-reassignment', 'commit'],
    mutationFn: (request: ReassignWrittenMaterialRequest) => client.reassign(request),
  })
}

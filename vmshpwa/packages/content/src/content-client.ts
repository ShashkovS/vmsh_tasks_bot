import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  contentEtagSchema,
  contentIfMatchSchema,
  contentAssetUploadKindSchema,
  contentMaterialKindSchema,
  problemMatchMutationRequestSchema,
  problemMatchReviewSchema,
  problemMetadataGridSchema,
  problemMetadataMutationRequestSchema,
  contentPublicationCancellationSchema,
  contentPublicationHidingSchema,
  contentPublicationSchema,
  contentQueryKeys,
  emptyContentMutationRequestSchema,
  parseRuntimeConfigForAudience,
  publishContentRequestSchema,
  publicIdSchema,
  publishedContentSchema,
  rollbackContentRequestSchema,
  staffContentHistorySchema,
  staffContentAssetUploadSchema,
  staffContentPreviewSchema,
  staffContentRevisionAssetsSchema,
  staffContentRevisionSchema,
  staffContentUploadTargetsSchema,
  type Audience,
  type ContentEtag,
  type ContentAssetUploadKind,
  type ContentIfMatch,
  type ContentMaterialKind,
  type ContentPublication,
  type ContentPublicationCancellation,
  type ContentPublicationHiding,
  type PublishedContent,
  type RuntimeConfig,
  type BusinessTimezone,
  type LocalPublicationTime,
  type ProblemMatchMutationRow,
  type ProblemMatchReview,
  type ProblemMetadataGrid,
  type ProblemMetadataMutationRow,
  type StaffContentHistory,
  type StaffContentAssetUpload,
  type StaffContentPreview,
  type StaffContentRevisionAssets,
  type StaffContentRevision,
  type StaffContentUploadTargets,
} from '@vmsh/contracts'

/**
 * Same-origin browser adapter for the Phase-2 content routes. It validates
 * every response before a renderer sees it and never exposes the compiler AST.
 * See `dev/development-plan/06-phase-2-content.md`.
 */

interface ResponseParser<T> {
  parse(payload: unknown): T
}

export interface VersionedContentResource<T> {
  data: T
  etag: ContentEtag
}

export interface UploadContentSourceInput {
  groupLessonId: string
  kind: ContentMaterialKind
  logicalFilename: string
  source: Blob
}

export interface UploadContentRevisionAssetInput {
  revisionId: string
  etag: ContentEtag
  logicalName: string
  kind: ContentAssetUploadKind
  asset?: File
}

export interface PublicationSlotVersion {
  publicationId: string
  version: number
  etag: ContentEtag
}

export interface PublishContentInput {
  groupLessonId: string
  kind: ContentMaterialKind
  revisionId: string
  mode: 'publish' | 'schedule'
  scheduledLocalTime?: LocalPublicationTime
  businessTimezone?: BusinessTimezone
  current?: PublicationSlotVersion
  scheduled?: PublicationSlotVersion
}

export interface PublishedContentInput {
  groupLessonId: string
  kind: ContentMaterialKind
  studentPublicId?: string
}

export interface ResolveProblemMatchesInput {
  revisionId: string
  etag: ContentEtag
  matches: ProblemMatchMutationRow[]
}

export interface SaveProblemMetadataGridInput {
  groupLessonId: string
  revisionId: string
  etag: ContentEtag
  rows: ProblemMetadataMutationRow[]
}

export interface ContentRequestOptions {
  signal?: AbortSignal
}

export interface ContentApiClient {
  readonly audience: Audience
  uploadSource(
    input: UploadContentSourceInput,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<StaffContentRevision>>
  uploadTargets(
    groupLessonId: string,
    options?: ContentRequestOptions,
  ): Promise<StaffContentUploadTargets>
  compileRevision(
    revisionId: string,
    etag: ContentEtag,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<StaffContentRevision>>
  diagnostics(
    revisionId: string,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<StaffContentRevision>>
  revisionAssets(
    revisionId: string,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<StaffContentRevisionAssets>>
  problemMatches(
    revisionId: string,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ProblemMatchReview>>
  resolveProblemMatches(
    input: ResolveProblemMatchesInput,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ProblemMatchReview>>
  metadataGrid(
    groupLessonId: string,
    revisionId: string,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ProblemMetadataGrid>>
  saveMetadataGrid(
    input: SaveProblemMetadataGridInput,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ProblemMetadataGrid>>
  uploadRevisionAsset(
    input: UploadContentRevisionAssetInput,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<StaffContentAssetUpload>>
  preview(
    revisionId: string,
    kind: 'web' | 'telegram' | 'pdf',
    options?: ContentRequestOptions,
  ): Promise<StaffContentPreview>
  history(groupLessonId: string, options?: ContentRequestOptions): Promise<StaffContentHistory>
  publish(
    input: PublishContentInput,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ContentPublication>>
  rollback(
    current: PublicationSlotVersion,
    revisionId: string,
    scheduled?: PublicationSlotVersion,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ContentPublication>>
  cancelScheduled(
    current: PublicationSlotVersion,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ContentPublicationCancellation>>
  hidePublished(
    current: PublicationSlotVersion,
    options?: ContentRequestOptions,
  ): Promise<VersionedContentResource<ContentPublicationHiding>>
  published(
    input: PublishedContentInput,
    options?: ContentRequestOptions,
  ): Promise<PublishedContent>
}

export interface ContentApiClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export class ContentProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'ContentProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class ContentNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Content request could not reach the server', { cause: options.cause })
    this.name = 'ContentNetworkError'
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function safeLogicalFilename(value: string): string {
  if (
    value.length < 1 ||
    value.length > 240 ||
    value !== value.trim() ||
    !value.toLocaleLowerCase('en-US').endsWith('.tex') ||
    value.startsWith('/') ||
    value.includes('\\') ||
    value.split('/').some((part) => !part || part === '.' || part === '..')
  ) {
    throw new TypeError('LaTeX filename must be a safe relative .tex path')
  }
  return value
}

function validatedPublicationSlot(
  slot: PublicationSlotVersion | undefined,
): PublicationSlotVersion | undefined {
  if (!slot) return undefined
  const publicationId = publicIdSchema.parse(slot.publicationId)
  if (!Number.isSafeInteger(slot.version) || slot.version < 1) {
    throw new TypeError('Publication version must be a positive safe integer')
  }
  const etag = contentEtagSchema.parse(slot.etag)
  if (etag !== `"${publicationId}:v${slot.version}"`) {
    throw new TypeError('Publication ETag must match its public ID and version')
  }
  return { publicationId, version: slot.version, etag }
}

class BrowserContentApiClient implements ContentApiClient {
  readonly audience: Audience

  readonly #apiBase: string
  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession?: () => Promise<unknown>

  constructor(runtime: RuntimeConfig, options: ContentApiClientOptions) {
    const parsedRuntime = parseRuntimeConfigForAudience(runtime.audience, runtime)
    this.audience = parsedRuntime.audience
    this.#apiBase = parsedRuntime.apiBase
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    if (options.refreshSession) this.#refreshSession = options.refreshSession
  }

  async uploadSource(
    input: UploadContentSourceInput,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<StaffContentRevision>> {
    this.#requireStaff()
    const groupLessonId = publicIdSchema.parse(input.groupLessonId)
    const kind = contentMaterialKindSchema.parse(input.kind)
    const logicalFilename = safeLogicalFilename(input.logicalFilename)
    const body = new FormData()
    body.set('groupLessonId', groupLessonId)
    body.set('kind', kind)
    body.set('logicalFilename', logicalFilename)
    body.set('source', input.source, logicalFilename.split('/').at(-1))
    return this.#versionedJson(
      '/content/uploads',
      { method: 'POST', body, ...options },
      staffContentRevisionSchema,
    )
  }

  async uploadTargets(
    groupLessonId: string,
    options: ContentRequestOptions = {},
  ): Promise<StaffContentUploadTargets> {
    this.#requireStaff()
    return this.#json(
      `/content/group-lessons/${encodeURIComponent(publicIdSchema.parse(groupLessonId))}/upload-targets`,
      { method: 'GET', ...options },
      staffContentUploadTargetsSchema,
    )
  }

  async compileRevision(
    revisionId: string,
    etag: ContentEtag,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<StaffContentRevision>> {
    this.#requireStaff()
    return this.#versionedJson(
      `/content/revisions/${encodeURIComponent(publicIdSchema.parse(revisionId))}/compile`,
      { method: 'POST', ifMatch: contentEtagSchema.parse(etag), ...options },
      staffContentRevisionSchema,
    )
  }

  async diagnostics(
    revisionId: string,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<StaffContentRevision>> {
    this.#requireStaff()
    return this.#versionedJson(
      `/content/uploads/${encodeURIComponent(publicIdSchema.parse(revisionId))}/diagnostics`,
      { method: 'GET', ...options },
      staffContentRevisionSchema,
    )
  }

  async revisionAssets(
    revisionId: string,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<StaffContentRevisionAssets>> {
    this.#requireStaff()
    return this.#versionedJson(
      `/content/revisions/${encodeURIComponent(publicIdSchema.parse(revisionId))}/assets`,
      { method: 'GET', ...options },
      staffContentRevisionAssetsSchema,
    )
  }

  async uploadRevisionAsset(
    input: UploadContentRevisionAssetInput,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<StaffContentAssetUpload>> {
    this.#requireStaff()
    const revisionId = publicIdSchema.parse(input.revisionId)
    const kind = contentAssetUploadKindSchema.parse(input.kind)
    const logicalName = input.logicalName.trim()
    if (!logicalName || logicalName.length > 2_000 || logicalName !== input.logicalName) {
      throw new TypeError('Asset logical name must be non-empty and trimmed')
    }
    if (kind === 'tikz' && input.asset !== undefined) {
      throw new TypeError('TikZ generation uses the exact stored revision and accepts no file')
    }
    if (kind !== 'tikz' && input.asset === undefined) {
      throw new TypeError('Raster and SVG asset uploads require a file')
    }

    const body = new FormData()
    body.set('logicalName', logicalName)
    body.set('kind', kind)
    if (input.asset) body.set('asset', input.asset, input.asset.name)
    return this.#versionedJson(
      `/content/revisions/${encodeURIComponent(revisionId)}/assets`,
      { method: 'POST', body, ifMatch: contentEtagSchema.parse(input.etag), ...options },
      staffContentAssetUploadSchema,
    )
  }

  async problemMatches(
    revisionId: string,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ProblemMatchReview>> {
    this.#requireStaff()
    return this.#reviewResource(
      `/content/revisions/${encodeURIComponent(publicIdSchema.parse(revisionId))}/problem-matches`,
      { method: 'GET', ...options },
      problemMatchReviewSchema,
    )
  }

  async resolveProblemMatches(
    input: ResolveProblemMatchesInput,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ProblemMatchReview>> {
    this.#requireStaff()
    const revisionId = publicIdSchema.parse(input.revisionId)
    const request = problemMatchMutationRequestSchema.parse({ matches: input.matches })
    return this.#reviewResource(
      `/content/revisions/${encodeURIComponent(revisionId)}/problem-matches`,
      {
        method: 'PUT',
        body: JSON.stringify(request),
        ifMatch: contentEtagSchema.parse(input.etag),
        contentType: 'application/json',
        ...options,
      },
      problemMatchReviewSchema,
    )
  }

  async metadataGrid(
    groupLessonId: string,
    revisionId: string,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ProblemMetadataGrid>> {
    this.#requireStaff()
    const query = new URLSearchParams({ revisionId: publicIdSchema.parse(revisionId) })
    return this.#reviewResource(
      `/group-lessons/${encodeURIComponent(publicIdSchema.parse(groupLessonId))}/metadata-grid?${query.toString()}`,
      { method: 'GET', ...options },
      problemMetadataGridSchema,
    )
  }

  async saveMetadataGrid(
    input: SaveProblemMetadataGridInput,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ProblemMetadataGrid>> {
    this.#requireStaff()
    const groupLessonId = publicIdSchema.parse(input.groupLessonId)
    const request = problemMetadataMutationRequestSchema.parse({
      revisionId: publicIdSchema.parse(input.revisionId),
      rows: input.rows,
    })
    return this.#reviewResource(
      `/group-lessons/${encodeURIComponent(groupLessonId)}/metadata-grid`,
      {
        method: 'PUT',
        body: JSON.stringify(request),
        ifMatch: contentEtagSchema.parse(input.etag),
        contentType: 'application/json',
        ...options,
      },
      problemMetadataGridSchema,
    )
  }

  async preview(
    revisionId: string,
    kind: 'web' | 'telegram' | 'pdf',
    options: ContentRequestOptions = {},
  ): Promise<StaffContentPreview> {
    this.#requireStaff()
    return this.#json(
      `/content/revisions/${encodeURIComponent(publicIdSchema.parse(revisionId))}/previews/${kind}`,
      { method: 'GET', ...options },
      staffContentPreviewSchema,
    )
  }

  async history(
    groupLessonId: string,
    options: ContentRequestOptions = {},
  ): Promise<StaffContentHistory> {
    this.#requireStaff()
    const query = new URLSearchParams({
      groupLesson: publicIdSchema.parse(groupLessonId),
    })
    return this.#json(
      `/publications?${query.toString()}`,
      { method: 'GET', ...options },
      staffContentHistorySchema,
    )
  }

  async publish(
    input: PublishContentInput,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ContentPublication>> {
    this.#requireStaff()
    const mode = input.mode
    const scheduledLocalTime = mode === 'schedule' ? input.scheduledLocalTime : undefined
    const businessTimezone = mode === 'schedule' ? input.businessTimezone : undefined
    if (mode === 'schedule' && (!scheduledLocalTime || !businessTimezone)) {
      throw new TypeError('A scheduled publication needs local time and business timezone')
    }
    if (
      mode === 'publish' &&
      (input.scheduledLocalTime !== undefined || input.businessTimezone !== undefined)
    ) {
      throw new TypeError('An immediate publication cannot carry schedule fields')
    }
    const current = validatedPublicationSlot(input.current)
    const scheduled = validatedPublicationSlot(input.scheduled)
    if (
      mode === 'schedule' &&
      ((current === undefined) !== (scheduled === undefined) ||
        (current !== undefined &&
          scheduled !== undefined &&
          (current.publicationId !== scheduled.publicationId ||
            current.version !== scheduled.version ||
            current.etag !== scheduled.etag)))
    ) {
      throw new TypeError('Scheduled publication preconditions must describe one exact slot')
    }
    const ifMatch = contentIfMatchSchema.parse(current?.etag ?? '"none"')
    const request = publishContentRequestSchema.parse({
      groupLessonId: publicIdSchema.parse(input.groupLessonId),
      kind: contentMaterialKindSchema.parse(input.kind),
      revisionId: publicIdSchema.parse(input.revisionId),
      mode,
      scheduledLocalTime: scheduledLocalTime ?? null,
      businessTimezone: businessTimezone ?? null,
      expectedCurrentPublicationId: current ? publicIdSchema.parse(current.publicationId) : null,
      expectedCurrentVersion: current ? current.version : null,
      expectedScheduledPublicationId: scheduled
        ? publicIdSchema.parse(scheduled.publicationId)
        : null,
      expectedScheduledVersion: scheduled ? scheduled.version : null,
    })
    const body = JSON.stringify(request)
    return this.#versionedJson(
      '/publications',
      { method: 'POST', body, ifMatch, contentType: 'application/json', ...options },
      contentPublicationSchema,
    )
  }

  async rollback(
    current: PublicationSlotVersion,
    revisionId: string,
    scheduled?: PublicationSlotVersion,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ContentPublication>> {
    this.#requireStaff()
    const validatedCurrent = validatedPublicationSlot(current)!
    const validatedScheduled = validatedPublicationSlot(scheduled)
    return this.#versionedJson(
      `/publications/${encodeURIComponent(validatedCurrent.publicationId)}/rollback`,
      {
        method: 'POST',
        body: JSON.stringify(
          rollbackContentRequestSchema.parse({
            revisionId: publicIdSchema.parse(revisionId),
            expectedScheduledPublicationId: validatedScheduled
              ? validatedScheduled.publicationId
              : null,
            expectedScheduledVersion: validatedScheduled ? validatedScheduled.version : null,
          }),
        ),
        ifMatch: validatedCurrent.etag,
        contentType: 'application/json',
        ...options,
      },
      contentPublicationSchema,
    )
  }

  async cancelScheduled(
    current: PublicationSlotVersion,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ContentPublicationCancellation>> {
    this.#requireStaff()
    const validatedCurrent = validatedPublicationSlot(current)!
    return this.#versionedJson(
      `/publications/${encodeURIComponent(validatedCurrent.publicationId)}/cancel`,
      {
        method: 'POST',
        body: JSON.stringify(emptyContentMutationRequestSchema.parse({})),
        ifMatch: validatedCurrent.etag,
        contentType: 'application/json',
        ...options,
      },
      contentPublicationCancellationSchema,
    )
  }

  async hidePublished(
    current: PublicationSlotVersion,
    options: ContentRequestOptions = {},
  ): Promise<VersionedContentResource<ContentPublicationHiding>> {
    this.#requireStaff()
    const validatedCurrent = validatedPublicationSlot(current)!
    return this.#versionedJson(
      `/publications/${encodeURIComponent(validatedCurrent.publicationId)}/hide`,
      {
        method: 'POST',
        body: JSON.stringify(emptyContentMutationRequestSchema.parse({})),
        ifMatch: validatedCurrent.etag,
        contentType: 'application/json',
        ...options,
      },
      contentPublicationHidingSchema,
    )
  }

  async published(
    input: PublishedContentInput,
    options: ContentRequestOptions = {},
  ): Promise<PublishedContent> {
    const groupLessonId = encodeURIComponent(publicIdSchema.parse(input.groupLessonId))
    const kind = contentMaterialKindSchema.parse(input.kind)
    let path: string
    if (this.audience === 'student') {
      if (input.studentPublicId !== undefined) {
        throw new TypeError('Student content read cannot select another student')
      }
      path = `/group-lessons/${groupLessonId}/content/${kind}`
    } else if (this.audience === 'family') {
      const studentPublicId = publicIdSchema.parse(input.studentPublicId)
      path = `/children/${encodeURIComponent(studentPublicId)}/group-lessons/${groupLessonId}/content/${kind}`
    } else {
      throw new TypeError('Staff cannot use the Student/Family published-content endpoint')
    }
    return this.#json(path, { method: 'GET', ...options }, publishedContentSchema)
  }

  #requireStaff(): void {
    if (this.audience !== 'staff')
      throw new TypeError('Staff content mutation requires Staff runtime')
  }

  async #versionedJson<T>(
    path: string,
    request: ContentTransportRequest,
    parser: ResponseParser<T>,
  ): Promise<VersionedContentResource<T>> {
    const response = await this.#request(path, request)
    const data = await this.#parseJsonResponse(response, parser)
    const etag = contentEtagSchema.safeParse(response.headers.get('ETag'))
    if (!etag.success) {
      throw new ContentProtocolError('Versioned content response has no valid ETag', {
        cause: etag.error,
        status: response.status,
      })
    }
    return { data, etag: etag.data }
  }

  async #reviewResource<T extends { etag: ContentEtag }>(
    path: string,
    request: ContentTransportRequest,
    parser: ResponseParser<T>,
  ): Promise<VersionedContentResource<T>> {
    const resource = await this.#versionedJson(path, request, parser)
    if (resource.data.etag !== resource.etag) {
      throw new ContentProtocolError('Review response ETag does not match its body', {
        status: 200,
      })
    }
    return resource
  }

  async #json<T>(
    path: string,
    request: ContentTransportRequest,
    parser: ResponseParser<T>,
  ): Promise<T> {
    return this.#parseJsonResponse(await this.#request(path, request), parser)
  }

  async #request(path: string, request: ContentTransportRequest): Promise<Response> {
    let response = await this.#send(path, request)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, request)
    }
    if (!response.ok) throw await this.#responseError(response)
    return response
  }

  async #send(path: string, request: ContentTransportRequest): Promise<Response> {
    const headers = new Headers({ Accept: 'application/json' })
    if (request.ifMatch) headers.set('If-Match', request.ifMatch)
    if (request.contentType) headers.set('Content-Type', request.contentType)
    try {
      return await this.#fetch(`${this.#apiBase}${path}`, {
        method: request.method,
        cache: 'no-store',
        credentials: 'include',
        headers,
        redirect: 'error',
        ...(request.body === undefined ? {} : { body: request.body }),
        ...(request.signal === undefined ? {} : { signal: request.signal }),
      })
    } catch (error) {
      if (isAbortError(error)) throw error
      throw new ContentNetworkError({ cause: error })
    }
  }

  async #parseJsonResponse<T>(response: Response, parser: ResponseParser<T>): Promise<T> {
    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new ContentProtocolError('Content API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return parser.parse(payload)
    } catch (error) {
      throw new ContentProtocolError('Content API response failed contract validation', {
        cause: error,
        status: response.status,
      })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new ContentProtocolError('Content API returned an invalid error envelope', {
        cause: error,
        status: response.status,
      })
    }
  }
}

interface ContentTransportRequest extends ContentRequestOptions {
  method: 'GET' | 'POST' | 'PUT'
  body?: BodyInit
  ifMatch?: ContentIfMatch
  contentType?: string
}

export function createContentApiClient(
  runtime: RuntimeConfig,
  options: ContentApiClientOptions = {},
): ContentApiClient {
  return new BrowserContentApiClient(runtime, options)
}

export function usePublishedContentQuery(
  client: ContentApiClient,
  input: PublishedContentInput,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.published(
      client.audience === 'family' ? 'family' : 'student',
      input.groupLessonId,
      input.kind,
      input.studentPublicId,
    ),
    queryFn: ({ signal }) => client.published(input, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useContentDiagnosticsQuery(
  client: ContentApiClient,
  revisionId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.diagnostics(revisionId),
    queryFn: ({ signal }) => client.diagnostics(revisionId, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useContentRevisionAssetsQuery(
  client: Pick<ContentApiClient, 'revisionAssets'>,
  revisionId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.assets(revisionId),
    queryFn: ({ signal }) => client.revisionAssets(revisionId, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useProblemMatchesQuery(
  client: Pick<ContentApiClient, 'problemMatches'>,
  revisionId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.problemMatches(revisionId),
    queryFn: ({ signal }) => client.problemMatches(revisionId, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useProblemMetadataGridQuery(
  client: Pick<ContentApiClient, 'metadataGrid'>,
  groupLessonId: string,
  revisionId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.metadataGrid(groupLessonId, revisionId),
    queryFn: ({ signal }) => client.metadataGrid(groupLessonId, revisionId, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useStaffContentHistoryQuery(
  client: ContentApiClient,
  groupLessonId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.history(groupLessonId),
    queryFn: ({ signal }) => client.history(groupLessonId, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useContentUploadTargetsQuery(
  client: Pick<ContentApiClient, 'uploadTargets'>,
  groupLessonId: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.uploadTargets(groupLessonId),
    queryFn: ({ signal }) => client.uploadTargets(groupLessonId, { signal }),
    enabled: options.enabled ?? true,
  })
}

export function useContentPreviewQuery(
  client: ContentApiClient,
  revisionId: string,
  kind: 'web' | 'telegram' | 'pdf',
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: contentQueryKeys.preview(revisionId, kind),
    queryFn: ({ signal }) => client.preview(revisionId, kind, { signal }),
    enabled: options.enabled ?? true,
  })
}

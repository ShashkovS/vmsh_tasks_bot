import {
  ApiResponseError,
  apiErrorSchema,
  changeClassroomStatusRequestSchema,
  classroomAssignmentHistoryResponseSchema,
  classroomAssignmentPlanEtag,
  classroomAssignmentPlanResponseSchema,
  classroomDeliveryBatchResponseSchema,
  classroomDeliveryPreviewResponseSchema,
  classroomEtag,
  classroomLayoutEtag,
  classroomLayoutResponseSchema,
  classroomListQuerySchema,
  classroomListResponseSchema,
  classroomResponseSchema,
  createClassroomRequestSchema,
  createClassroomDeliveryBatchRequestSchema,
  confirmClassroomLayoutRequestSchema,
  confirmClassroomAssignmentPlanRequestSchema,
  materializeClassroomLayoutRequestSchema,
  latestClassroomDeliveryBatchResponseSchema,
  inPersonEventEtag,
  inPersonEventListResponseSchema,
  inPersonEventResponseSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  recalculateClassroomAssignmentPlanRequestSchema,
  renameClassroomRequestSchema,
  replaceClassroomLayoutRequestSchema,
  retryClassroomDeliveryBatchRequestSchema,
  saveInPersonEventRequestSchema,
  updateClassroomAssignmentPlanRequestSchema,
  type ChangeClassroomStatusRequest,
  type Classroom,
  type ClassroomAssignmentHistoryResponse,
  type ClassroomAssignmentPlanResponse,
  type ClassroomDeliveryBatchResponse,
  type ClassroomDeliveryPreviewResponse,
  type ClassroomListQuery,
  type ClassroomListResponse,
  type ClassroomLayoutResponse,
  type ClassroomResponse,
  type CreateClassroomRequest,
  type CreateClassroomDeliveryBatchRequest,
  type ConfirmClassroomLayoutRequest,
  type ConfirmClassroomAssignmentPlanRequest,
  type MaterializeClassroomLayoutRequest,
  type LatestClassroomDeliveryBatchResponse,
  type InPersonEvent,
  type InPersonEventListResponse,
  type InPersonEventResponse,
  type RenameClassroomRequest,
  type RecalculateClassroomAssignmentPlanRequest,
  type ReplaceClassroomLayoutRequest,
  type RetryClassroomDeliveryBatchRequest,
  type SaveInPersonEventRequest,
  type RuntimeConfig,
  type UpdateClassroomAssignmentPlanRequest,
} from '@vmsh/contracts'

export interface ClassroomRequestOptions {
  signal?: AbortSignal
}

export interface ClassroomClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface ClassroomClient {
  listInPersonEvents(options?: ClassroomRequestOptions): Promise<InPersonEventListResponse>
  createInPersonEvent(
    request: SaveInPersonEventRequest,
    options?: ClassroomRequestOptions,
  ): Promise<InPersonEventResponse>
  updateInPersonEvent(
    event: InPersonEvent,
    request: SaveInPersonEventRequest,
    options?: ClassroomRequestOptions,
  ): Promise<InPersonEventResponse>
  list(
    query?: ClassroomListQuery,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomListResponse>
  create(
    request: CreateClassroomRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomResponse>
  rename(
    classroom: Classroom,
    request: RenameClassroomRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomResponse>
  archive(
    classroom: Classroom,
    request: ChangeClassroomStatusRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomResponse>
  restore(
    classroom: Classroom,
    request: ChangeClassroomStatusRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomResponse>
  getLayout(
    eventPublicId: string,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomLayoutResponse>
  materializeLayout(
    eventPublicId: string,
    request: MaterializeClassroomLayoutRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomLayoutResponse>
  replaceLayout(
    eventPublicId: string,
    layout: { publicId: string; version: number },
    request: ReplaceClassroomLayoutRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomLayoutResponse>
  confirmLayout(
    eventPublicId: string,
    layout: { publicId: string; version: number },
    request: ConfirmClassroomLayoutRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomLayoutResponse>
  getAssignmentPlan(
    eventPublicId: string,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomAssignmentPlanResponse>
  getAssignmentHistory(
    eventPublicId: string,
    planPublicId: string,
    enrollmentPublicId: string,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomAssignmentHistoryResponse>
  recalculateAssignmentPlan(
    eventPublicId: string,
    plan: { publicId: string; version: number } | null,
    request: RecalculateClassroomAssignmentPlanRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomAssignmentPlanResponse>
  updateAssignmentPlan(
    eventPublicId: string,
    plan: { publicId: string; version: number },
    request: UpdateClassroomAssignmentPlanRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomAssignmentPlanResponse>
  confirmAssignmentPlan(
    eventPublicId: string,
    plan: { publicId: string; version: number },
    request: ConfirmClassroomAssignmentPlanRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomAssignmentPlanResponse>
  previewAssignmentDelivery(
    planPublicId: string,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomDeliveryPreviewResponse>
  createAssignmentDelivery(
    planPublicId: string,
    request: CreateClassroomDeliveryBatchRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomDeliveryBatchResponse>
  getAssignmentDelivery(
    batchPublicId: string,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomDeliveryBatchResponse>
  getLatestAssignmentDelivery(
    planPublicId: string,
    options?: ClassroomRequestOptions,
  ): Promise<LatestClassroomDeliveryBatchResponse>
  retryFailedAssignmentDelivery(
    batchPublicId: string,
    request: RetryClassroomDeliveryBatchRequest,
    options?: ClassroomRequestOptions,
  ): Promise<ClassroomDeliveryBatchResponse>
}

export class ClassroomProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'ClassroomProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class ClassroomNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Classroom request could not reach the server', { cause: options.cause })
    this.name = 'ClassroomNetworkError'
  }
}

class BrowserClassroomClient implements ClassroomClient {
  readonly #apiBase: string
  readonly #fetch: typeof globalThis.fetch
  readonly #refreshSession: (() => Promise<unknown>) | undefined

  constructor(runtime: RuntimeConfig, options: ClassroomClientOptions) {
    this.#apiBase = parseRuntimeConfigForAudience('staff', runtime).apiBase
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
    this.#refreshSession = options.refreshSession
  }

  async listInPersonEvents(
    options: ClassroomRequestOptions = {},
  ): Promise<InPersonEventListResponse> {
    return this.#request('/in-person-events', { method: 'GET' }, options, 200, (payload) =>
      inPersonEventListResponseSchema.parse(payload),
    )
  }

  async createInPersonEvent(
    request: SaveInPersonEventRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<InPersonEventResponse> {
    return this.#request(
      '/in-person-events',
      { method: 'POST', body: JSON.stringify(saveInPersonEventRequestSchema.parse(request)) },
      options,
      201,
      (payload) => inPersonEventResponseSchema.parse(payload),
    )
  }

  async updateInPersonEvent(
    event: InPersonEvent,
    request: SaveInPersonEventRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<InPersonEventResponse> {
    const publicId = publicIdSchema.parse(event.publicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(publicId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(saveInPersonEventRequestSchema.parse(request)),
        headers: { 'If-Match': inPersonEventEtag(event) },
      },
      options,
      200,
      (payload) => inPersonEventResponseSchema.parse(payload),
    )
  }

  async list(
    query: ClassroomListQuery = {},
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomListResponse> {
    const parsed = classroomListQuerySchema.parse(query)
    const search = new URLSearchParams({ status: parsed.status })
    if (parsed.search) search.set('search', parsed.search)
    return this.#request(
      `/classrooms?${search.toString()}`,
      { method: 'GET' },
      options,
      200,
      (payload) => classroomListResponseSchema.parse(payload),
    )
  }

  async create(
    request: CreateClassroomRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomResponse> {
    return this.#request(
      '/classrooms',
      { method: 'POST', body: JSON.stringify(createClassroomRequestSchema.parse(request)) },
      options,
      201,
      (payload) => classroomResponseSchema.parse(payload),
    )
  }

  async rename(
    classroom: Classroom,
    request: RenameClassroomRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomResponse> {
    return this.#mutate(
      classroom,
      '',
      'PATCH',
      renameClassroomRequestSchema.parse(request),
      options,
    )
  }

  async archive(
    classroom: Classroom,
    request: ChangeClassroomStatusRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomResponse> {
    return this.#mutate(
      classroom,
      '/archive',
      'POST',
      changeClassroomStatusRequestSchema.parse(request),
      options,
    )
  }

  async restore(
    classroom: Classroom,
    request: ChangeClassroomStatusRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomResponse> {
    return this.#mutate(
      classroom,
      '/restore',
      'POST',
      changeClassroomStatusRequestSchema.parse(request),
      options,
    )
  }

  async getLayout(
    eventPublicId: string,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomLayoutResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-layout`,
      { method: 'GET' },
      options,
      200,
      (payload) => classroomLayoutResponseSchema.parse(payload),
    )
  }

  async materializeLayout(
    eventPublicId: string,
    request: MaterializeClassroomLayoutRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomLayoutResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-layout/materialize`,
      {
        method: 'POST',
        body: JSON.stringify(materializeClassroomLayoutRequestSchema.parse(request)),
      },
      options,
      200,
      (payload) => classroomLayoutResponseSchema.parse(payload),
    )
  }

  async replaceLayout(
    eventPublicId: string,
    layout: { publicId: string; version: number },
    request: ReplaceClassroomLayoutRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomLayoutResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    const publicId = publicIdSchema.parse(layout.publicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-layout/${encodeURIComponent(publicId)}/rooms`,
      {
        method: 'PUT',
        body: JSON.stringify(replaceClassroomLayoutRequestSchema.parse(request)),
        headers: { 'If-Match': classroomLayoutEtag({ ...layout, publicId }) },
      },
      options,
      200,
      (payload) => classroomLayoutResponseSchema.parse(payload),
    )
  }

  async confirmLayout(
    eventPublicId: string,
    layout: { publicId: string; version: number },
    request: ConfirmClassroomLayoutRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomLayoutResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    const publicId = publicIdSchema.parse(layout.publicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-layout/${encodeURIComponent(publicId)}/confirm`,
      {
        method: 'POST',
        body: JSON.stringify(confirmClassroomLayoutRequestSchema.parse(request)),
        headers: { 'If-Match': classroomLayoutEtag({ ...layout, publicId }) },
      },
      options,
      200,
      (payload) => classroomLayoutResponseSchema.parse(payload),
    )
  }

  async getAssignmentPlan(
    eventPublicId: string,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomAssignmentPlanResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-assignment-plan`,
      { method: 'GET' },
      options,
      200,
      (payload) => classroomAssignmentPlanResponseSchema.parse(payload),
    )
  }

  async getAssignmentHistory(
    eventPublicId: string,
    planPublicId: string,
    enrollmentPublicId: string,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomAssignmentHistoryResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    const planId = publicIdSchema.parse(planPublicId)
    const enrollmentId = publicIdSchema.parse(enrollmentPublicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-assignment-plan/${encodeURIComponent(planId)}/students/${encodeURIComponent(enrollmentId)}/history`,
      { method: 'GET' },
      options,
      200,
      (payload) => classroomAssignmentHistoryResponseSchema.parse(payload),
    )
  }

  async recalculateAssignmentPlan(
    eventPublicId: string,
    plan: { publicId: string; version: number } | null,
    request: RecalculateClassroomAssignmentPlanRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomAssignmentPlanResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-assignment-plan/recalculate`,
      {
        method: 'POST',
        body: JSON.stringify(recalculateClassroomAssignmentPlanRequestSchema.parse(request)),
        ...(plan === null ? {} : { headers: { 'If-Match': classroomAssignmentPlanEtag(plan) } }),
      },
      options,
      200,
      (payload) => classroomAssignmentPlanResponseSchema.parse(payload),
    )
  }

  async updateAssignmentPlan(
    eventPublicId: string,
    plan: { publicId: string; version: number },
    request: UpdateClassroomAssignmentPlanRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomAssignmentPlanResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    const publicId = publicIdSchema.parse(plan.publicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-assignment-plan/${encodeURIComponent(publicId)}/assignments`,
      {
        method: 'PUT',
        body: JSON.stringify(updateClassroomAssignmentPlanRequestSchema.parse(request)),
        headers: { 'If-Match': classroomAssignmentPlanEtag({ ...plan, publicId }) },
      },
      options,
      200,
      (payload) => classroomAssignmentPlanResponseSchema.parse(payload),
    )
  }

  async confirmAssignmentPlan(
    eventPublicId: string,
    plan: { publicId: string; version: number },
    request: ConfirmClassroomAssignmentPlanRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomAssignmentPlanResponse> {
    const eventId = publicIdSchema.parse(eventPublicId)
    const publicId = publicIdSchema.parse(plan.publicId)
    return this.#request(
      `/in-person-events/${encodeURIComponent(eventId)}/classroom-assignment-plan/${encodeURIComponent(publicId)}/confirm`,
      {
        method: 'POST',
        body: JSON.stringify(confirmClassroomAssignmentPlanRequestSchema.parse(request)),
        headers: { 'If-Match': classroomAssignmentPlanEtag({ ...plan, publicId }) },
      },
      options,
      200,
      (payload) => classroomAssignmentPlanResponseSchema.parse(payload),
    )
  }

  async previewAssignmentDelivery(
    planPublicId: string,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomDeliveryPreviewResponse> {
    const planId = publicIdSchema.parse(planPublicId)
    return this.#request(
      `/classroom-assignment-plans/${encodeURIComponent(planId)}/delivery-preview`,
      { method: 'POST', body: JSON.stringify({ schemaVersion: 1 }) },
      options,
      200,
      (payload) => classroomDeliveryPreviewResponseSchema.parse(payload),
    )
  }

  async createAssignmentDelivery(
    planPublicId: string,
    request: CreateClassroomDeliveryBatchRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomDeliveryBatchResponse> {
    const planId = publicIdSchema.parse(planPublicId)
    return this.#request(
      `/classroom-assignment-plans/${encodeURIComponent(planId)}/delivery-batches`,
      {
        method: 'POST',
        body: JSON.stringify(createClassroomDeliveryBatchRequestSchema.parse(request)),
      },
      options,
      201,
      (payload) => classroomDeliveryBatchResponseSchema.parse(payload),
    )
  }

  async getAssignmentDelivery(
    batchPublicId: string,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomDeliveryBatchResponse> {
    const batchId = publicIdSchema.parse(batchPublicId)
    return this.#request(
      `/classroom-assignment-delivery-batches/${encodeURIComponent(batchId)}`,
      { method: 'GET' },
      options,
      200,
      (payload) => classroomDeliveryBatchResponseSchema.parse(payload),
    )
  }

  async getLatestAssignmentDelivery(
    planPublicId: string,
    options: ClassroomRequestOptions = {},
  ): Promise<LatestClassroomDeliveryBatchResponse> {
    const planId = publicIdSchema.parse(planPublicId)
    return this.#request(
      `/classroom-assignment-plans/${encodeURIComponent(planId)}/delivery-latest`,
      { method: 'GET' },
      options,
      200,
      (payload) => latestClassroomDeliveryBatchResponseSchema.parse(payload),
    )
  }

  async retryFailedAssignmentDelivery(
    batchPublicId: string,
    request: RetryClassroomDeliveryBatchRequest,
    options: ClassroomRequestOptions = {},
  ): Promise<ClassroomDeliveryBatchResponse> {
    const batchId = publicIdSchema.parse(batchPublicId)
    return this.#request(
      `/classroom-assignment-delivery-batches/${encodeURIComponent(batchId)}/retry-failed`,
      {
        method: 'POST',
        body: JSON.stringify(retryClassroomDeliveryBatchRequestSchema.parse(request)),
      },
      options,
      200,
      (payload) => classroomDeliveryBatchResponseSchema.parse(payload),
    )
  }

  async #mutate(
    classroom: Classroom,
    suffix: string,
    method: 'PATCH' | 'POST',
    request: RenameClassroomRequest | ChangeClassroomStatusRequest,
    options: ClassroomRequestOptions,
  ): Promise<ClassroomResponse> {
    const publicId = publicIdSchema.parse(classroom.publicId)
    return this.#request(
      `/classrooms/${encodeURIComponent(publicId)}${suffix}`,
      {
        method,
        body: JSON.stringify(request),
        headers: { 'If-Match': classroomEtag(classroom) },
      },
      options,
      200,
      (payload) => classroomResponseSchema.parse(payload),
    )
  }

  async #request<T>(
    path: string,
    init: {
      method: 'GET' | 'POST' | 'PATCH' | 'PUT'
      body?: string
      headers?: Record<string, string>
    },
    options: ClassroomRequestOptions,
    expectedStatus: number,
    parse: (payload: unknown) => T,
  ): Promise<T> {
    let response = await this.#send(path, init, options)
    if (response.status === 401 && this.#refreshSession) {
      await response.body?.cancel()
      await this.#refreshSession()
      response = await this.#send(path, init, options)
    }
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== expectedStatus) {
      await response.body?.cancel()
      throw new ClassroomProtocolError(
        `Classroom API returned unexpected HTTP ${response.status}`,
        { status: response.status },
      )
    }
    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new ClassroomProtocolError('Classroom API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }
    try {
      return parse(payload)
    } catch (error) {
      throw new ClassroomProtocolError('Classroom API response failed contract validation', {
        cause: error,
        status: response.status,
      })
    }
  }

  async #send(
    path: string,
    init: {
      method: 'GET' | 'POST' | 'PATCH' | 'PUT'
      body?: string
      headers?: Record<string, string>
    },
    options: ClassroomRequestOptions,
  ): Promise<Response> {
    const headers = {
      Accept: 'application/json',
      ...(init.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...init.headers,
    }
    try {
      return await this.#fetch(`${this.#apiBase}${path}`, {
        method: init.method,
        cache: 'no-store',
        credentials: 'include',
        headers,
        redirect: 'error',
        ...(init.body === undefined ? {} : { body: init.body }),
        ...(options.signal === undefined ? {} : { signal: options.signal }),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ClassroomNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    try {
      const payload: unknown = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new ClassroomProtocolError('Classroom API returned an invalid error envelope', {
        cause: error,
        status: response.status,
      })
    }
  }
}

export function createClassroomClient(
  runtime: RuntimeConfig,
  options: ClassroomClientOptions = {},
): ClassroomClient {
  return new BrowserClassroomClient(runtime, options)
}

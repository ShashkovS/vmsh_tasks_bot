import {
  ApiResponseError,
  apiErrorSchema,
  changeClassroomStatusRequestSchema,
  classroomEtag,
  classroomListQuerySchema,
  classroomListResponseSchema,
  classroomResponseSchema,
  createClassroomRequestSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  renameClassroomRequestSchema,
  type ChangeClassroomStatusRequest,
  type Classroom,
  type ClassroomListQuery,
  type ClassroomListResponse,
  type ClassroomResponse,
  type CreateClassroomRequest,
  type RenameClassroomRequest,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface ClassroomRequestOptions {
  signal?: AbortSignal
}

export interface ClassroomClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshSession?: () => Promise<unknown>
}

export interface ClassroomClient {
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
    init: { method: 'GET' | 'POST' | 'PATCH'; body?: string; headers?: Record<string, string> },
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
    init: { method: 'GET' | 'POST' | 'PATCH'; body?: string; headers?: Record<string, string> },
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

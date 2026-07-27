import {
  ApiResponseError,
  apiErrorSchema,
  authContextSchema,
  authSessionsResponseSchema,
  familyLoginRequestSchema,
  parseRuntimeConfigForAudience,
  sessionPublicIdSchema,
  staffLoginRequestSchema,
  studentLoginRequestSchema,
  type Audience,
  type AuthContext,
  type AuthSessionsResponse,
  type FamilyLoginRequest,
  type RuntimeConfig,
  type SessionPublicId,
  type StaffLoginRequest,
  type StudentLoginRequest,
} from '@vmsh/contracts'

import {
  createBrowserAuthRefreshCoordinator,
  type AuthRefreshCoordinator,
} from './auth-refresh-coordinator'

/**
 * Browser authentication transport for Phase 1.
 *
 * The audience and API base are fixed by the validated runtime rather than a
 * request body or caller-provided URL. See `dev/development-plan/05-phase-1-auth.md`.
 */

export type AuthLoginRequest<A extends Audience = Audience> = A extends 'student'
  ? StudentLoginRequest
  : A extends 'family'
    ? FamilyLoginRequest
    : StaffLoginRequest

export interface AuthRequestOptions {
  signal?: AbortSignal
}

export interface AuthClientOptions {
  fetchImplementation?: typeof globalThis.fetch
  refreshCoordinator?: AuthRefreshCoordinator
}

export class AuthProtocolError extends Error {
  readonly status?: number

  constructor(message: string, options: { cause?: unknown; status?: number } = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'AuthProtocolError'
    if (options.status !== undefined) this.status = options.status
  }
}

export class AuthAudienceMismatchError extends AuthProtocolError {
  constructor(expected: Audience, received: Audience) {
    super(`Authentication response audience does not match ${expected}`)
    this.name = 'AuthAudienceMismatchError'
    // Deliberately omit account/session identifiers and the response payload.
    void received
  }
}

export class AuthNetworkError extends Error {
  constructor(options: { cause: unknown }) {
    super('Authentication request could not reach the server', { cause: options.cause })
    this.name = 'AuthNetworkError'
  }
}

export type AuthApiAccessFailure = 'unauthenticated' | 'forbidden' | 'other'

export type AuthLoginFailure =
  'invalid' | 'rate-limited' | 'account-unavailable' | 'network' | 'error'

export function classifyAuthApiError(error: unknown): AuthApiAccessFailure {
  if (!(error instanceof ApiResponseError)) return 'other'
  if (error.status === 401) return 'unauthenticated'
  if (error.status === 403) return 'forbidden'
  return 'other'
}

export function classifyAuthLoginError(error: unknown): AuthLoginFailure {
  if (error instanceof AuthNetworkError) return 'network'
  if (!(error instanceof ApiResponseError)) return 'error'
  if (error.code === 'invalid_credentials') return 'invalid'
  if (error.code === 'rate_limited') return 'rate-limited'
  if (error.code === 'account_unavailable') return 'account-unavailable'
  return 'error'
}

export interface AuthClient<A extends Audience = Audience> {
  readonly audience: A
  readonly runtime: RuntimeConfig
  login(request: AuthLoginRequest<A>, options?: AuthRequestOptions): Promise<AuthContext>
  me(options?: AuthRequestOptions): Promise<AuthContext>
  refresh(options?: AuthRequestOptions): Promise<AuthContext>
  sessions(options?: AuthRequestOptions): Promise<AuthSessionsResponse>
  revokeSession(sessionId: SessionPublicId, options?: AuthRequestOptions): Promise<void>
  logout(options?: AuthRequestOptions): Promise<void>
  logoutAll(options?: AuthRequestOptions): Promise<void>
}

interface ResponseParser<T> {
  parse(payload: unknown): T
}

type HttpMethod = 'GET' | 'POST' | 'DELETE'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

class BrowserAuthClient<A extends Audience> implements AuthClient<A> {
  readonly audience: A
  readonly runtime: RuntimeConfig

  readonly #authBase: string
  readonly #fetch: typeof globalThis.fetch
  readonly #refreshCoordinator: AuthRefreshCoordinator
  #refreshGeneration = 0
  #refreshPromise: Promise<AuthContext> | null = null

  constructor(audience: A, runtime: RuntimeConfig, options: AuthClientOptions) {
    this.audience = audience
    this.runtime = parseRuntimeConfigForAudience(audience, runtime)
    this.#authBase = `${this.runtime.apiBase}/auth`
    this.#refreshCoordinator =
      options.refreshCoordinator ?? createBrowserAuthRefreshCoordinator(this.audience)
    const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
    // Calling a native Window.fetch as `this.#fetch(...)` gives it the client
    // instance as a receiver and throws `Illegal invocation` in real browsers.
    // The lexical wrapper preserves function-call semantics for both the
    // browser transport and injected test transports.
    this.#fetch = (...arguments_) => fetchImplementation(...arguments_)
  }

  async login(
    request: AuthLoginRequest<A>,
    options: AuthRequestOptions = {},
  ): Promise<AuthContext> {
    const body = this.#parseLoginRequest(request)
    return this.#requestJson(
      '/login',
      { method: 'POST', body: JSON.stringify(body), ...options },
      this.#authContextParser(),
      false,
    )
  }

  async me(options: AuthRequestOptions = {}): Promise<AuthContext> {
    return this.#requestJson('/me', { method: 'GET', ...options }, this.#authContextParser(), true)
  }

  async refresh(options: AuthRequestOptions = {}): Promise<AuthContext> {
    return this.#refreshOnce(options)
  }

  async sessions(options: AuthRequestOptions = {}): Promise<AuthSessionsResponse> {
    return this.#requestJson(
      '/sessions',
      { method: 'GET', ...options },
      this.#sessionsParser(),
      true,
    )
  }

  async revokeSession(sessionId: SessionPublicId, options: AuthRequestOptions = {}): Promise<void> {
    const parsedSessionId = sessionPublicIdSchema.parse(sessionId)
    await this.#requestNoContent(
      `/sessions/${encodeURIComponent(parsedSessionId)}`,
      { method: 'DELETE', ...options },
      true,
    )
  }

  async logout(options: AuthRequestOptions = {}): Promise<void> {
    await this.#requestNoContent('/logout', { method: 'POST', body: '{}', ...options }, true)
  }

  async logoutAll(options: AuthRequestOptions = {}): Promise<void> {
    await this.#requestNoContent('/logout-all', { method: 'POST', body: '{}', ...options }, true)
  }

  #parseLoginRequest(request: AuthLoginRequest<A>): AuthLoginRequest {
    switch (this.audience) {
      case 'student':
        return studentLoginRequestSchema.parse(request)
      case 'family':
        return familyLoginRequestSchema.parse(request)
      case 'staff':
        return staffLoginRequestSchema.parse(request)
    }
  }

  #authContextParser(): ResponseParser<AuthContext> {
    return {
      parse: (payload) => {
        const context = authContextSchema.parse(payload)
        if (context.principal.audience !== this.audience) {
          throw new AuthAudienceMismatchError(this.audience, context.principal.audience)
        }
        return context
      },
    }
  }

  #sessionsParser(): ResponseParser<AuthSessionsResponse> {
    return {
      parse: (payload) => {
        const response = authSessionsResponseSchema.parse(payload)
        if (response.audience !== this.audience) {
          throw new AuthAudienceMismatchError(this.audience, response.audience)
        }
        return response
      },
    }
  }

  async #requestJson<T>(
    path: string,
    request: AuthRequestOptions & { method: HttpMethod; body?: string },
    parser: ResponseParser<T>,
    allowRefresh: boolean,
  ): Promise<T> {
    const response = await this.#requestWithOptionalRefresh(path, request, allowRefresh)
    if (!response.ok) throw await this.#responseError(response)

    let payload: unknown
    try {
      payload = await response.json()
    } catch (error) {
      throw new AuthProtocolError('Authentication API returned malformed JSON', {
        cause: error,
        status: response.status,
      })
    }

    try {
      return parser.parse(payload)
    } catch (error) {
      if (error instanceof AuthProtocolError) throw error
      throw new AuthProtocolError('Authentication API response failed contract validation', {
        cause: error,
        status: response.status,
      })
    }
  }

  async #requestNoContent(
    path: string,
    request: AuthRequestOptions & { method: HttpMethod; body?: string },
    allowRefresh: boolean,
  ): Promise<void> {
    const response = await this.#requestWithOptionalRefresh(path, request, allowRefresh)
    if (!response.ok) throw await this.#responseError(response)
    if (response.status !== 204) {
      throw new AuthProtocolError('Authentication mutation must return 204 No Content', {
        status: response.status,
      })
    }
  }

  async #requestWithOptionalRefresh(
    path: string,
    request: AuthRequestOptions & { method: HttpMethod; body?: string },
    allowRefresh: boolean,
  ): Promise<Response> {
    const generationAtStart = this.#refreshGeneration
    let response = await this.#send(path, request)
    if (response.status !== 401 || !allowRefresh) return response

    await response.body?.cancel()
    if (generationAtStart === this.#refreshGeneration) {
      // A caller aborting its own request must not cancel the one refresh shared
      // by other requests. Its signal is still honored by the retry below.
      await this.#refreshOnce({})
    }
    response = await this.#send(path, request)
    return response
  }

  #refreshOnce(options: AuthRequestOptions): Promise<AuthContext> {
    if (this.#refreshPromise) return this.#refreshPromise

    this.#refreshPromise = this.#refreshCoordinator
      .coordinate(
        async () => {
          try {
            // Another tab may have rotated the shared cookies while this tab
            // waited for leadership. Recheck before consuming a single-use
            // refresh secret.
            return await this.#requestJson(
              '/me',
              { method: 'GET', ...options },
              this.#authContextParser(),
              false,
            )
          } catch (error) {
            if (!(error instanceof ApiResponseError) || error.status !== 401) throw error
          }
          return this.#requestJson(
            '/refresh',
            { method: 'POST', body: '{}', ...options },
            this.#authContextParser(),
            false,
          )
        },
        () =>
          // No Web Locks means no safe cross-tab leader election. A follower
          // may recover from another tab's completed rotation, but never sends
          // a competing refresh itself.
          this.#requestJson('/me', { method: 'GET', ...options }, this.#authContextParser(), false),
      )
      .finally(() => {
        // Advance after both success and failure. Requests that began before this
        // attempt must never trigger a second refresh when their delayed 401
        // arrives; a later user/request generation may try again explicitly.
        this.#refreshGeneration += 1
        this.#refreshPromise = null
      })
    return this.#refreshPromise
  }

  async #send(
    path: string,
    request: AuthRequestOptions & { method: HttpMethod; body?: string },
  ): Promise<Response> {
    const headers = new Headers({ Accept: 'application/json' })
    if (request.method !== 'GET') headers.set('Content-Type', 'application/json')

    try {
      return await this.#fetch(`${this.#authBase}${path}`, {
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
      throw new AuthNetworkError({ cause: error })
    }
  }

  async #responseError(response: Response): Promise<Error> {
    let payload: unknown
    try {
      payload = await response.json()
      return new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    } catch (error) {
      if (error instanceof ApiResponseError) return error
      return new AuthProtocolError('Authentication API returned an invalid error envelope', {
        cause: error,
        status: response.status,
      })
    }
  }
}

export function createAuthClient<A extends Audience>(
  audience: A,
  runtime: RuntimeConfig,
  options: AuthClientOptions = {},
): AuthClient<A> {
  return new BrowserAuthClient(audience, runtime, options)
}

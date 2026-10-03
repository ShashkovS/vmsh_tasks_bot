import { describe, expect, it, vi } from 'vitest'

import familyAuthFixture from '@vmsh/contracts/fixtures/auth/family.v1.json'
import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  sessionPublicIdSchema,
  studentLoginRequestSchema,
} from '@vmsh/contracts'

import {
  AuthAudienceMismatchError,
  AuthNetworkError,
  AuthProtocolError,
  classifyAuthLoginError,
  createAuthClient,
} from './auth-client'
import {
  createBrowserAuthRefreshCoordinator,
  createInMemoryAuthRefreshCoordinator,
  type AuthWebLockManager,
} from './auth-refresh-coordinator'

const studentRuntime = parseRuntimeConfigForAudience('student', studentRuntimeFixture.response)

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    status,
  })
}

function authErrorResponse(status: number, code: string): Response {
  return jsonResponse(
    {
      error: {
        code,
        message: 'Synthetic server copy',
        requestId: `request-${code}`,
      },
    },
    status,
  )
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function stringRequestBody(body: BodyInit | null | undefined): string {
  if (typeof body !== 'string') throw new TypeError('Expected a string request body')
  return body
}

function createStudentClient(fetchImplementation: typeof globalThis.fetch) {
  return createAuthClient('student', studentRuntime, {
    fetchImplementation,
    refreshCoordinator: createInMemoryAuthRefreshCoordinator(),
  })
}

function createSerialWebLockManager(): AuthWebLockManager {
  let tail = Promise.resolve()
  return {
    request<T>(_name: string, _options: { mode: 'exclusive' }, callback: () => Promise<T>) {
      const result = tail.then(callback, callback)
      tail = result.then(
        () => undefined,
        () => undefined,
      )
      return result
    },
  }
}

describe('browser authentication client', () => {
  it('invokes the fetch transport without an object receiver', async () => {
    const observedReceivers: unknown[] = []
    const fetchImplementation: typeof globalThis.fetch = function (this: unknown) {
      observedReceivers.push(this)
      return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
    }
    const client = createStudentClient(fetchImplementation)

    await client.me()

    expect(observedReceivers).toEqual([undefined])
  })

  it('maps login failures without exposing server details', () => {
    const apiFailure = (code: string) =>
      new ApiResponseError(
        401,
        apiErrorSchema.parse({
          error: { code, message: 'Synthetic', requestId: `request-${code}` },
        }),
      )

    expect(classifyAuthLoginError(apiFailure('invalid_credentials'))).toBe('invalid')
    expect(classifyAuthLoginError(apiFailure('rate_limited'))).toBe('rate-limited')
    expect(classifyAuthLoginError(apiFailure('account_unavailable'))).toBe('account-unavailable')
    expect(classifyAuthLoginError(new AuthNetworkError({ cause: new TypeError('offline') }))).toBe(
      'network',
    )
    expect(classifyAuthLoginError(apiFailure('unexpected'))).toBe('error')
  })

  it('uses only the validated audience URL and sends the audience-specific body with cookies', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(studentAuthFixture.authContext)),
    )
    const client = createStudentClient(fetchImplementation)
    const request = studentLoginRequestSchema.parse(studentAuthFixture.loginRequest)

    await expect(client.login(request)).resolves.toMatchObject({
      principal: { audience: 'student' },
    })

    expect(fetchImplementation).toHaveBeenCalledTimes(1)
    const [url, init] = fetchImplementation.mock.calls[0]!
    expect(url).toBe('/student/api/v1/auth/login')
    expect(init).toMatchObject({
      method: 'POST',
      cache: 'no-store',
      credentials: 'include',
      redirect: 'error',
    })
    expect(Object.fromEntries(new Headers(init?.headers))).toEqual({
      accept: 'application/json',
      'content-type': 'application/json',
    })
    expect(JSON.parse(stringRequestBody(init?.body))).toEqual(request)
    expect(JSON.parse(stringRequestBody(init?.body))).not.toHaveProperty('audience')
  })

  it('collapses concurrent 401 responses into one refresh and retries both requests once', async () => {
    let meCalls = 0
    let refreshCalls = 0
    let releaseRefresh: (() => void) | undefined
    const refreshGate = new Promise<void>((resolve) => {
      releaseRefresh = resolve
    })
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(async (input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        await refreshGate
        return jsonResponse(studentAuthFixture.authContext)
      }
      if (url.endsWith('/auth/me')) {
        meCalls += 1
        return meCalls <= 3
          ? authErrorResponse(401, 'session_expired')
          : jsonResponse(studentAuthFixture.authContext)
      }
      throw new Error(`Unexpected URL ${url}`)
    })
    const client = createStudentClient(fetchImplementation)

    const first = client.me()
    const second = client.me()
    await vi.waitFor(() => expect(refreshCalls).toBe(1))
    releaseRefresh?.()

    await expect(Promise.all([first, second])).resolves.toHaveLength(2)
    expect(refreshCalls).toBe(1)
    expect(meCalls).toBe(5)
  })

  it('coordinates two browser clients so only one consumes the shared refresh cookie', async () => {
    let accessValid = false
    let refreshCalls = 0
    let releaseRefresh: (() => void) | undefined
    const refreshGate = new Promise<void>((resolve) => {
      releaseRefresh = resolve
    })
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(async (input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        await refreshGate
        accessValid = true
        return jsonResponse(studentAuthFixture.authContext)
      }
      if (url.endsWith('/auth/me')) {
        return accessValid
          ? jsonResponse(studentAuthFixture.authContext)
          : authErrorResponse(401, 'session_expired')
      }
      throw new Error(`Unexpected URL ${url}`)
    })
    const lockManager = createSerialWebLockManager()
    const coordinatorOptions = {
      lockManager,
      notifyFallbackWaiters: () => undefined,
    }
    const firstClient = createAuthClient('student', studentRuntime, {
      fetchImplementation,
      refreshCoordinator: createBrowserAuthRefreshCoordinator('student', coordinatorOptions),
    })
    const secondClient = createAuthClient('student', studentRuntime, {
      fetchImplementation,
      refreshCoordinator: createBrowserAuthRefreshCoordinator('student', coordinatorOptions),
    })

    const first = firstClient.me()
    const second = secondClient.me()
    await vi.waitFor(() => expect(refreshCalls).toBe(1))
    releaseRefresh?.()

    await expect(Promise.all([first, second])).resolves.toHaveLength(2)
    expect(refreshCalls).toBe(1)
  })

  it('fails closed without Web Locks and only rechecks the current access cookie', async () => {
    let meCalls = 0
    let refreshCalls = 0
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      meCalls += 1
      return Promise.resolve(authErrorResponse(401, 'session_expired'))
    })
    const client = createAuthClient('student', studentRuntime, {
      fetchImplementation,
      refreshCoordinator: createBrowserAuthRefreshCoordinator('student', {
        lockManager: null,
        waitForFallbackSignal: () => Promise.resolve(),
      }),
    })

    await expect(client.me()).rejects.toMatchObject({ status: 401 })
    expect(meCalls).toBe(2)
    expect(refreshCalls).toBe(0)
  })

  it('does not enter a second refresh loop when the retried request is still unauthorized', async () => {
    let refreshCalls = 0
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      return Promise.resolve(authErrorResponse(401, 'session_revoked'))
    })
    const client = createStudentClient(fetchImplementation)

    await expect(client.me()).rejects.toMatchObject({
      status: 401,
      code: 'session_revoked',
    } satisfies Partial<ApiResponseError>)
    expect(refreshCalls).toBe(1)
  })

  it('does not start another refresh for a delayed 401 from the same failed generation', async () => {
    let meCalls = 0
    let refreshCalls = 0
    let releaseSecondUnauthorized: (() => void) | undefined
    const secondUnauthorizedGate = new Promise<void>((resolve) => {
      releaseSecondUnauthorized = resolve
    })
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(async (input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1
        return authErrorResponse(401, 'session_expired')
      }
      meCalls += 1
      if (meCalls === 2) await secondUnauthorizedGate
      return authErrorResponse(401, 'session_expired')
    })
    const client = createStudentClient(fetchImplementation)

    const first = client.me()
    const delayed = client.me()
    await expect(first).rejects.toMatchObject({ status: 401 })
    expect(refreshCalls).toBe(1)
    releaseSecondUnauthorized?.()

    await expect(delayed).rejects.toMatchObject({ status: 401 })
    expect(refreshCalls).toBe(1)
    expect(meCalls).toBe(4)
  })

  it('accepts an empty 204 logout response without attempting to parse JSON', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    )
    const client = createStudentClient(fetchImplementation)

    await expect(client.logout()).resolves.toBeUndefined()
    const [url, init] = fetchImplementation.mock.calls[0]!
    expect(url).toBe('/student/api/v1/auth/logout')
    expect(init).toMatchObject({ method: 'POST', credentials: 'include', body: '{}' })
  })

  it('revokes only a canonical backend session public ID', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(new Response(null, { status: 204 })),
    )
    const client = createStudentClient(fetchImplementation)
    const sessionId = sessionPublicIdSchema.parse('0123456789abcdef0123456789abcdef')

    await expect(client.revokeSession(sessionId)).resolves.toBeUndefined()
    const [url, init] = fetchImplementation.mock.calls[0]!
    expect(url).toBe('/student/api/v1/auth/sessions/0123456789abcdef0123456789abcdef')
    expect(init).toMatchObject({ method: 'DELETE', credentials: 'include' })
  })

  it('rejects a noncanonical session ID before sending a revoke request', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>()
    const client = createStudentClient(fetchImplementation)

    await expect(client.revokeSession('session-student-current' as never)).rejects.toThrow()
    expect(fetchImplementation).not.toHaveBeenCalled()
  })

  it('fails closed when a no-content mutation returns an undocumented success body', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse({ ok: true })),
    )
    const client = createStudentClient(fetchImplementation)

    await expect(client.logout()).rejects.toBeInstanceOf(AuthProtocolError)
  })

  it('wraps malformed successful JSON without leaking the response payload', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        jsonResponse({ principal: { audience: 'student', secret: 'must-not-leak' } }),
      ),
    )
    const client = createStudentClient(fetchImplementation)

    const error = await client.me().catch((reason: unknown) => reason)
    expect(error).toBeInstanceOf(AuthProtocolError)
    expect(String(error)).not.toContain('must-not-leak')
  })

  it('rejects a valid context belonging to another audience', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(familyAuthFixture.authContext)),
    )
    const client = createStudentClient(fetchImplementation)

    await expect(client.me()).rejects.toBeInstanceOf(AuthAudienceMismatchError)
  })

  it('rejects a valid single-audience session list belonging to another audience', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(familyAuthFixture.sessionsResponse)),
    )
    const client = createStudentClient(fetchImplementation)

    await expect(client.sessions()).rejects.toBeInstanceOf(AuthAudienceMismatchError)
  })

  it('rejects a runtime boundary for a different audience before making a request', () => {
    expect(() => createAuthClient('family', studentRuntime)).toThrow()
  })
})

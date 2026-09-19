import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { act, useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import familyAuthFixture from '@vmsh/contracts/fixtures/auth/family.v1.json'
import staffAuthFixture from '@vmsh/contracts/fixtures/auth/staff.v1.json'
import staffRuntimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import {
  ApiResponseError,
  apiErrorSchema,
  authContextSchema,
  parseRuntimeConfigForAudience,
  staffCapabilitySchema,
} from '@vmsh/contracts'

import {
  AuthenticationBoundary,
  AuthenticationRedirectBoundary,
  StaffCapabilityBoundary,
} from './auth-boundary'
import {
  AuthenticationProvider,
  useAuthentication,
  useAuthenticationLogin,
  type AuthenticationOfflineStore,
  type PersistedAuthenticationSnapshot,
} from './auth-context'
import { createInMemoryAuthRefreshCoordinator } from './auth-refresh-coordinator'
import { AppProviders, createAppQueryClient } from './providers'

const studentRuntime = parseRuntimeConfigForAudience('student', studentRuntimeFixture.response)
const staffRuntime = parseRuntimeConfigForAudience('staff', staffRuntimeFixture.response)
const studentAuthContext = authContextSchema.parse(studentAuthFixture.authContext)

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    status,
  })
}

function apiError(status: number, code: string): Response {
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

function authContextExpiringAt(sessionExpiresAt: string) {
  return {
    ...studentAuthFixture.authContext,
    currentSession: {
      ...studentAuthFixture.authContext.currentSession,
      expiresAt: sessionExpiresAt,
    },
    policy: {
      ...studentAuthFixture.authContext.policy,
      sessionExpiresAt,
    },
  }
}

function durableSnapshot(
  sessionExpiresAt = studentAuthFixture.authContext.policy.sessionExpiresAt,
): PersistedAuthenticationSnapshot {
  return {
    audience: 'student',
    ownerId: studentAuthContext.principal.accountId,
    principal: studentAuthContext.principal,
    sessionExpiresAt,
    cachedAt: '2026-07-27T08:00:00.000Z',
  }
}

function mockOfflineStore(snapshot: PersistedAuthenticationSnapshot | null) {
  const store = {
    read: vi.fn<AuthenticationOfflineStore['read']>(() => Promise.resolve(snapshot)),
    save: vi.fn<AuthenticationOfflineStore['save']>((context) =>
      Promise.resolve({
        audience: 'student',
        ownerId: context.principal.accountId,
        principal: context.principal,
        sessionExpiresAt: context.policy.sessionExpiresAt,
        cachedAt: '2026-07-27T08:00:01.000Z',
      }),
    ),
    clear: vi.fn<AuthenticationOfflineStore['clear']>(() => Promise.resolve()),
  } satisfies AuthenticationOfflineStore
  return store
}

function renderStudentBoundary(
  fetchImplementation: typeof globalThis.fetch,
  offlineStore?: AuthenticationOfflineStore,
) {
  const queryClient = createAppQueryClient()
  return render(
    <AppProviders queryClient={queryClient}>
      <AuthenticationProvider
        audience="student"
        fetchImplementation={fetchImplementation}
        {...(offlineStore ? { offlineStore } : {})}
        refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
        runtime={studentRuntime}
      >
        <AuthenticationBoundary>
          <p>Защищённое содержимое</p>
        </AuthenticationBoundary>
      </AuthenticationProvider>
    </AppProviders>,
  )
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('authentication provider and boundary', () => {
  it('does not mount protected children before a valid session is loaded', async () => {
    let resolveRequest: ((response: Response) => void) | undefined
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve
        }),
    )

    renderStudentBoundary(fetchImplementation)

    expect(screen.getByRole('status').textContent).toContain('Проверяем вход')
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()

    await act(async () => {
      resolveRequest?.(jsonResponse(studentAuthFixture.authContext))
      await Promise.resolve()
    })
    expect(await screen.findByText('Защищённое содержимое')).not.toBeNull()
  })

  it('turns a missing access and refresh session into unauthenticated without rendering children', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(apiError(401, 'authentication_required')),
    )

    renderStudentBoundary(fetchImplementation)

    expect(await screen.findByText('Требуется вход')).not.toBeNull()
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
    // The refresh leader rechecks `/me` after acquiring the cross-tab lock
    // before it is allowed to consume the single-use refresh cookie.
    expect(fetchImplementation).toHaveBeenCalledTimes(3)
  })

  it('requests one login redirect without ever mounting protected children', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(apiError(401, 'authentication_required')),
    )
    const onAuthenticationRequired = vi.fn()
    const queryClient = createAppQueryClient()

    render(
      <AppProviders queryClient={queryClient}>
        <AuthenticationProvider
          audience="student"
          fetchImplementation={fetchImplementation}
          refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
          runtime={studentRuntime}
        >
          <AuthenticationRedirectBoundary onAuthenticationRequired={onAuthenticationRequired}>
            <p>Нельзя смонтировать</p>
          </AuthenticationRedirectBoundary>
        </AuthenticationProvider>
      </AppProviders>,
    )

    expect(
      await screen.findByText('Открываем страницу входа и сохраним адрес этого раздела.'),
    ).not.toBeNull()
    expect(onAuthenticationRequired).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Нельзя смонтировать')).toBeNull()
  })

  it('moves from an anonymous check through login and a confirmed 204 logout', async () => {
    let authenticated = false
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/login')) {
        authenticated = true
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      if (url.endsWith('/auth/logout')) {
        authenticated = false
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      if (url.endsWith('/auth/me') && authenticated) {
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      return Promise.resolve(apiError(401, 'authentication_required'))
    })

    function AuthControls() {
      const authentication = useAuthentication()
      return (
        <>
          <button
            onClick={() => void authentication.login(studentAuthFixture.loginRequest)}
            type="button"
          >
            Войти в тесте
          </button>
          <AuthenticationBoundary unauthenticatedFallback={<p>Сессии нет</p>}>
            <button onClick={() => void authentication.logout()} type="button">
              Выйти из теста
            </button>
          </AuthenticationBoundary>
        </>
      )
    }

    const queryClient = createAppQueryClient()
    const offlineStore = mockOfflineStore(null)
    render(
      <AppProviders queryClient={queryClient}>
        <AuthenticationProvider
          audience="student"
          fetchImplementation={fetchImplementation}
          offlineStore={offlineStore}
          refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
          runtime={studentRuntime}
        >
          <AuthControls />
        </AuthenticationProvider>
      </AppProviders>,
    )

    expect(await screen.findByText('Сессии нет')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Войти в тесте' }))
    expect(await screen.findByRole('button', { name: 'Выйти из теста' })).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Выйти из теста' }))
    expect(await screen.findByText('Сессии нет')).not.toBeNull()

    expect(fetchImplementation.mock.calls.map(([input]) => requestUrl(input))).toEqual([
      '/student/api/v1/auth/me',
      '/student/api/v1/auth/me',
      '/student/api/v1/auth/refresh',
      '/student/api/v1/auth/login',
      '/student/api/v1/auth/logout',
    ])
    expect(offlineStore.save).toHaveBeenCalledWith(studentAuthFixture.authContext)
    expect(offlineStore.clear).toHaveBeenCalledTimes(2)
  })

  it('drives pending, rate-limited and authenticated public-login states', async () => {
    let loginAttempts = 0
    let releaseSecondLogin: (() => void) | undefined
    const secondLoginGate = new Promise<void>((resolve) => {
      releaseSecondLogin = resolve
    })
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(async (input) => {
      const url = requestUrl(input)
      if (!url.endsWith('/auth/login')) {
        return apiError(401, 'authentication_required')
      }
      loginAttempts += 1
      if (loginAttempts === 1) return apiError(429, 'rate_limited')
      await secondLoginGate
      return jsonResponse(studentAuthFixture.authContext)
    })
    const onAuthenticated = vi.fn()
    let currentSubmission: Promise<boolean> | undefined

    function LoginProbe() {
      const authentication = useAuthentication()
      const login = useAuthenticationLogin(onAuthenticated)
      return (
        <div>
          <span>{login.loginState}</span>
          <span data-testid="authentication-status">{authentication.state.status}</span>
          <button
            onClick={() => {
              currentSubmission = login.submit(studentAuthFixture.loginRequest)
            }}
            type="button"
          >
            Отправить вход
          </button>
        </div>
      )
    }

    const queryClient = createAppQueryClient()
    render(
      <AppProviders queryClient={queryClient}>
        <AuthenticationProvider
          audience="student"
          fetchImplementation={fetchImplementation}
          refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
          runtime={studentRuntime}
        >
          <LoginProbe />
        </AuthenticationProvider>
      </AppProviders>,
    )

    expect(await screen.findByText('idle')).not.toBeNull()
    await vi.waitFor(() =>
      expect(screen.getByTestId('authentication-status').textContent).toBe('unauthenticated'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Отправить вход' }))
    expect(await screen.findByText('rate-limited')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Отправить вход' }))
    expect(await screen.findByText('pending')).not.toBeNull()

    let loginSucceeded: boolean | undefined
    await act(async () => {
      releaseSecondLogin?.()
      await secondLoginGate
      loginSucceeded = await currentSubmission
    })
    expect(loginSucceeded).toBe(true)
    await vi.waitFor(() =>
      expect(screen.getByTestId('authentication-status').textContent).toBe('authenticated'),
    )
    await vi.waitFor(() => expect(onAuthenticated).toHaveBeenCalledTimes(1))
  })

  it('fails closed on cold-start network failure and on a wrong-audience context', async () => {
    const offlineFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.reject(new TypeError('synthetic offline')),
    )
    const offlineView = renderStudentBoundary(offlineFetch)
    await vi.waitFor(() => expect(screen.queryByText('Не удалось проверить вход')).not.toBeNull())
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
    offlineView.unmount()

    const wrongAudienceFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(familyAuthFixture.authContext)),
    )
    renderStudentBoundary(wrongAudienceFetch)
    expect(await screen.findByText('Не удалось безопасно открыть кабинет')).not.toBeNull()
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
    expect(screen.queryByText('Synthetic server copy')).toBeNull()
  })

  it('unlocks only the previous owner cache on a secret-free cold-offline snapshot', async () => {
    vi.useFakeTimers()
    vi.setSystemTime('2026-07-28T08:00:00.000Z')
    const offlineFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.reject(new TypeError('synthetic offline')),
    )
    const offlineStore = mockOfflineStore(durableSnapshot())

    renderStudentBoundary(offlineFetch, offlineStore)

    await vi.waitFor(() => expect(screen.queryByText('Защищённое содержимое')).not.toBeNull())
    expect(offlineStore.read).toHaveBeenCalledOnce()
    expect(offlineStore.save).not.toHaveBeenCalled()
  })

  it('clears a durable owner snapshot after an authoritative session rejection', async () => {
    const rejectedFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(apiError(401, 'session_revoked')),
    )
    const offlineStore = mockOfflineStore(durableSnapshot())

    renderStudentBoundary(rejectedFetch, offlineStore)

    await vi.waitFor(() => expect(screen.queryByText('Требуется вход')).not.toBeNull())
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
    expect(offlineStore.clear).toHaveBeenCalledOnce()
  })

  it('does not unlock a durable snapshot past its server-owned expiry', async () => {
    vi.useFakeTimers()
    vi.setSystemTime('2026-08-10T08:00:00.000Z')
    const offlineFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.reject(new TypeError('synthetic offline')),
    )
    const offlineStore = mockOfflineStore(durableSnapshot('2026-08-09T21:00:00.000Z'))

    renderStudentBoundary(offlineFetch, offlineStore)

    await vi.waitFor(() => expect(screen.queryByText('Требуется вход')).not.toBeNull())
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
    expect(offlineStore.clear).toHaveBeenCalledOnce()
  })

  it('unmounts protected content at the absolute server session expiry', async () => {
    vi.useFakeTimers()
    vi.setSystemTime('2026-07-27T08:00:00.000Z')
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(authContextExpiringAt('2026-07-27T08:00:05.000Z'))),
    )

    renderStudentBoundary(fetchImplementation)
    await vi.waitFor(() => expect(screen.queryByText('Защищённое содержимое')).not.toBeNull())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_001)
    })

    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
    expect(screen.getByText('Требуется вход')).not.toBeNull()
  })

  it('keeps a previously verified shell explicitly offline only before expiry', async () => {
    vi.useFakeTimers()
    vi.setSystemTime('2026-07-27T08:00:00.000Z')
    let offline = false
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      offline
        ? Promise.reject(new TypeError('synthetic offline'))
        : Promise.resolve(jsonResponse(authContextExpiringAt('2026-07-27T08:00:05.000Z'))),
    )

    function OfflineStateProbe() {
      const authentication = useAuthentication()
      return (
        <>
          <span data-testid="auth-state">{authentication.state.status}</span>
          <button
            onClick={() => {
              void authentication.retry().catch(() => undefined)
            }}
            type="button"
          >
            Проверить снова
          </button>
          <AuthenticationBoundary>
            <p>Кешированное защищённое содержимое</p>
          </AuthenticationBoundary>
        </>
      )
    }

    render(
      <AppProviders queryClient={createAppQueryClient()}>
        <AuthenticationProvider
          audience="student"
          fetchImplementation={fetchImplementation}
          refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
          runtime={studentRuntime}
        >
          <OfflineStateProbe />
        </AuthenticationProvider>
      </AppProviders>,
    )

    await vi.waitFor(() =>
      expect(screen.getByTestId('auth-state').textContent).toBe('authenticated'),
    )
    offline = true
    fireEvent.click(screen.getByRole('button', { name: 'Проверить снова' }))
    await vi.waitFor(() =>
      expect(screen.getByTestId('auth-state').textContent).toBe('offline-unverified'),
    )
    expect(screen.getByText('Кешированное защищённое содержимое')).not.toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_001)
    })
    expect(screen.getByTestId('auth-state').textContent).toBe('unauthenticated')
    expect(screen.queryByText('Кешированное защищённое содержимое')).toBeNull()
  })

  it('never mounts a context that is already past its absolute expiry', async () => {
    vi.useFakeTimers()
    vi.setSystemTime('2026-07-27T08:00:00.000Z')
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(authContextExpiringAt('2026-07-27T07:59:59.000Z'))),
    )

    renderStudentBoundary(fetchImplementation)
    await vi.waitFor(() => expect(screen.queryByText('Требуется вход')).not.toBeNull())
    expect(screen.queryByText('Защищённое содержимое')).toBeNull()
  })

  it('keeps a 403 session authenticated but clears protected state on a later 401', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(studentAuthFixture.authContext)),
    )

    function AccessProbe() {
      const authentication = useAuthentication()
      const [classification, setClassification] = useState('none')
      const failure = (status: 401 | 403, code: 'session_revoked' | 'forbidden') =>
        new ApiResponseError(
          status,
          apiErrorSchema.parse({
            error: { code, message: 'Synthetic', requestId: `request-${status}` },
          }),
        )
      return (
        <div>
          <span>{classification}</span>
          <button
            onClick={() =>
              setClassification(authentication.handleApiError(failure(403, 'forbidden')))
            }
            type="button"
          >
            Запрет
          </button>
          <button
            onClick={() =>
              setClassification(authentication.handleApiError(failure(401, 'session_revoked')))
            }
            type="button"
          >
            Отзыв
          </button>
        </div>
      )
    }

    const queryClient = createAppQueryClient()
    render(
      <AppProviders queryClient={queryClient}>
        <AuthenticationProvider
          audience="student"
          fetchImplementation={fetchImplementation}
          refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
          runtime={studentRuntime}
        >
          <AuthenticationBoundary>
            <AccessProbe />
          </AuthenticationBoundary>
        </AuthenticationProvider>
      </AppProviders>,
    )
    await screen.findByRole('button', { name: 'Запрет' })

    fireEvent.click(screen.getByRole('button', { name: 'Запрет' }))
    expect(screen.getByText('forbidden')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Отзыв' })).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Отзыв' }))
    expect(await screen.findByText('Требуется вход')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Запрет' })).toBeNull()
  })

  it('uses Staff capabilities only as a UI gate and never promotes a teacher by role', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(staffAuthFixture.authContext)),
    )
    const queryClient = createAppQueryClient()
    render(
      <AppProviders queryClient={queryClient}>
        <AuthenticationProvider
          audience="staff"
          fetchImplementation={fetchImplementation}
          refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
          runtime={staffRuntime}
        >
          <AuthenticationBoundary>
            <StaffCapabilityBoundary capability={staffCapabilitySchema.parse('review.write')}>
              <p>Проверка разрешена</p>
            </StaffCapabilityBoundary>
            <StaffCapabilityBoundary capability={staffCapabilitySchema.parse('audit.read')}>
              <p>Аудит разрешён</p>
            </StaffCapabilityBoundary>
          </AuthenticationBoundary>
        </AuthenticationProvider>
      </AppProviders>,
    )

    expect(await screen.findByText('Проверка разрешена')).not.toBeNull()
    expect(screen.queryByText('Аудит разрешён')).toBeNull()
    expect(screen.getByText('Нет доступа')).not.toBeNull()
  })
})

it('keeps refresh identity stable when authority refetches, preserving live queues', async () => {
  const callbacks: Array<ReturnType<typeof useAuthentication>['refresh']> = []
  function Probe() {
    const auth = useAuthentication()
    callbacks.push(auth.refresh)
    return <button onClick={() => void auth.refresh()}>Refresh authority</button>
  }
  const fetchImplementation = vi.fn<typeof fetch>(() =>
    Promise.resolve(jsonResponse(studentAuthContext)),
  )
  render(
    <AppProviders queryClient={createAppQueryClient()}>
      <AuthenticationProvider
        refreshCoordinator={createInMemoryAuthRefreshCoordinator()}
        audience="student"
        runtime={studentRuntime}
        fetchImplementation={fetchImplementation}
      >
        <AuthenticationBoundary>
          <Probe />
        </AuthenticationBoundary>
      </AuthenticationProvider>
    </AppProviders>,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Refresh authority' }))
  await vi.waitFor(() => expect(fetchImplementation).toHaveBeenCalledTimes(2))
  expect(new Set(callbacks).size).toBe(1)
})

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import familyAuthFixture from '@vmsh/contracts/fixtures/auth/family.v1.json'
import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import {
  authSessionsResponseSchema,
  parseRuntimeConfigForAudience,
  type AuthSessionSummary,
} from '@vmsh/contracts'

import { AuthenticationBoundary } from './auth-boundary'
import { AuthenticationProvider } from './auth-context'
import { AppProviders, createAppQueryClient } from './providers'
import { AccountSessionManager, type SessionOfflineWorkGuard } from './session-management'

const runtime = parseRuntimeConfigForAudience('student', studentRuntimeFixture.response)
const parsedFixtureSessions = authSessionsResponseSchema.parse(
  studentAuthFixture.sessionsResponse,
).sessions

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    status,
  })
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function renderManager(
  fetchImplementation: typeof globalThis.fetch,
  offlineWorkGuard?: SessionOfflineWorkGuard,
) {
  return render(
    <AppProviders queryClient={createAppQueryClient()}>
      <AuthenticationProvider
        audience="student"
        fetchImplementation={fetchImplementation}
        runtime={runtime}
      >
        <AuthenticationBoundary unauthenticatedFallback={<p>Сессия завершена</p>}>
          <AccountSessionManager
            {...(offlineWorkGuard === undefined ? {} : { offlineWorkGuard })}
          />
        </AuthenticationBoundary>
      </AuthenticationProvider>
    </AppProviders>,
  )
}

afterEach(() => cleanup())

describe('account session manager', () => {
  it('loads the real session endpoint and revokes one other device after confirmation', async () => {
    let sessions: AuthSessionSummary[] = [...parsedFixtureSessions]
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input, init) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/me')) {
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      if (url.endsWith('/auth/sessions') && init?.method === 'GET') {
        return Promise.resolve(jsonResponse({ audience: 'student', sessions }))
      }
      if (url.endsWith(`/auth/sessions/${parsedFixtureSessions[1]!.sessionId}`)) {
        sessions = sessions.filter(
          (session) => session.sessionId !== parsedFixtureSessions[1]!.sessionId,
        )
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      throw new Error(`Unexpected synthetic request: ${url}`)
    })

    renderManager(fetchImplementation)

    const revoke = await screen.findByRole('button', {
      name: /завершить сессию на устройстве Synthetic Mobile/i,
    })
    expect(document.body.textContent).not.toContain(parsedFixtureSessions[0]!.sessionId)
    expect(document.body.textContent).not.toContain(parsedFixtureSessions[1]!.sessionId)

    fireEvent.click(revoke)
    fireEvent.click(await screen.findByRole('button', { name: 'Подтвердить' }))

    await waitFor(() =>
      expect(
        screen.queryByRole('button', {
          name: /завершить сессию на устройстве Synthetic Mobile/i,
        }),
      ).toBeNull(),
    )
    expect(
      fetchImplementation.mock.calls.some(
        ([input, init]) =>
          requestUrl(input).endsWith(`/auth/sessions/${parsedFixtureSessions[1]!.sessionId}`) &&
          init?.method === 'DELETE',
      ),
    ).toBe(true)
  })

  it('warns about pending offline work before current logout and runs deferred cleanup after 204', async () => {
    const order: string[] = []
    const afterConfirmedSessionEnd = vi.fn(() => {
      order.push('cleanup')
      return Promise.resolve()
    })
    const offlineWorkGuard: SessionOfflineWorkGuard = {
      inspect: () => ({ status: 'pending', queuedCount: 1 }),
      afterConfirmedSessionEnd,
    }
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/me')) {
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      if (url.endsWith('/auth/sessions')) {
        return Promise.resolve(jsonResponse(studentAuthFixture.sessionsResponse))
      }
      if (url.endsWith('/auth/logout')) {
        order.push('server')
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      throw new Error(`Unexpected synthetic request: ${url}`)
    })

    renderManager(fetchImplementation, offlineWorkGuard)

    fireEvent.click(await screen.findByRole('button', { name: 'Выйти на этом устройстве' }))
    expect((await screen.findByRole('alert')).textContent).toContain('1 неотправленное действие')
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить' }))

    expect(await screen.findByText('Сессия завершена')).not.toBeNull()
    await waitFor(() => expect(afterConfirmedSessionEnd).toHaveBeenCalledTimes(1))
    expect(order).toEqual(['server', 'cleanup'])
    expect(
      fetchImplementation.mock.calls.some(([input]) => requestUrl(input).endsWith('/auth/logout')),
    ).toBe(true)
  })

  it('fails closed when the offline-work inspection cannot complete', async () => {
    const offlineWorkGuard: SessionOfflineWorkGuard = {
      inspect: () => Promise.reject(new Error('Synthetic storage failure')),
    }
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/me')) {
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      if (url.endsWith('/auth/sessions')) {
        return Promise.resolve(jsonResponse(studentAuthFixture.sessionsResponse))
      }
      if (url.endsWith('/auth/logout')) {
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      throw new Error(`Unexpected synthetic request: ${url}`)
    })

    renderManager(fetchImplementation, offlineWorkGuard)

    fireEvent.click(await screen.findByRole('button', { name: 'Выйти на этом устройстве' }))
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain(
        'Не удалось проверить локальную очередь',
      ),
    )
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(
      fetchImplementation.mock.calls.some(([input]) => requestUrl(input).endsWith('/auth/logout')),
    ).toBe(false)
  })

  it('does not render a valid session list belonging to another audience', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const url = requestUrl(input)
      if (url.endsWith('/auth/me')) {
        return Promise.resolve(jsonResponse(studentAuthFixture.authContext))
      }
      if (url.endsWith('/auth/sessions')) {
        return Promise.resolve(jsonResponse(familyAuthFixture.sessionsResponse))
      }
      throw new Error(`Unexpected synthetic request: ${url}`)
    })

    renderManager(fetchImplementation)

    expect(await screen.findByText('Не удалось безопасно открыть список сессий')).not.toBeNull()
    expect(screen.queryByRole('list', { name: 'Активные сессии' })).toBeNull()
    expect(screen.queryByRole('button', { name: /выйти на всех/i })).toBeNull()
  })
})

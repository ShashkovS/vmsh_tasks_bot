import { cleanup, render, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { parseRuntimeConfigForAudience, type RuntimeConfig } from '@vmsh/contracts'

import { AuthenticationProvider } from './auth-context'
import { AppProviders, createAppQueryClient } from './providers'
import { RealtimeProvider, type RealtimeEnvironment, type RealtimeSocket } from './realtime'

const studentRuntime: RuntimeConfig = parseRuntimeConfigForAudience(
  'student',
  studentRuntimeFixture.response,
)

class ProviderSocket implements RealtimeSocket {
  readyState = 0
  onopen: ((event: unknown) => void) | null = null
  onerror: ((event: unknown) => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  readonly closes: number[] = []

  send(): void {}

  close(code = 1000): void {
    this.readyState = 3
    this.closes.push(code)
  }
}

function providerEnvironment(): RealtimeEnvironment {
  return {
    isOnline: () => true,
    isVisible: () => true,
    listen: () => () => undefined,
    random: () => 0.5,
    setTimeout: (callback, delayMilliseconds) => window.setTimeout(callback, delayMilliseconds),
    clearTimeout: (handle) => window.clearTimeout(handle),
  }
}

afterEach(() => cleanup())

describe('RealtimeProvider authentication composition', () => {
  it('creates no socket before authentication and leaves one live socket after StrictMode cleanup', async () => {
    let resolveAuthentication: ((response: Response) => void) | undefined
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(
      () =>
        new Promise<Response>((resolve) => {
          resolveAuthentication = resolve
        }),
    )
    const sockets: ProviderSocket[] = []
    const environment = providerEnvironment()
    const queryClient = createAppQueryClient()
    const view = render(
      <StrictMode>
        <AppProviders queryClient={queryClient}>
          <AuthenticationProvider
            audience="student"
            fetchImplementation={fetchImplementation}
            runtime={studentRuntime}
          >
            <RealtimeProvider
              audience="student"
              environment={environment}
              runtime={studentRuntime}
              socketFactory={() => {
                const socket = new ProviderSocket()
                sockets.push(socket)
                return socket
              }}
            >
              <p>Приложение</p>
            </RealtimeProvider>
          </AuthenticationProvider>
        </AppProviders>
      </StrictMode>,
    )

    expect(sockets).toHaveLength(0)
    resolveAuthentication?.(
      new Response(JSON.stringify(studentAuthFixture.authContext), {
        headers: { 'Content-Type': 'application/json' },
        status: 200,
      }),
    )
    await waitFor(() => expect(sockets.length).toBeGreaterThan(0))
    expect(sockets.filter((socket) => socket.closes.length === 0)).toHaveLength(1)

    view.unmount()
    expect(sockets.filter((socket) => socket.closes.length === 0)).toHaveLength(0)
    expect(sockets.every((socket) => socket.closes.at(-1) === 1000)).toBe(true)
  })
})

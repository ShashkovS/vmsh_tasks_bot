import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createBrowserStorageNamespace } from '@vmsh/contracts'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'

import { AppProviders, ThemeToggle, themeStorageKey } from './providers'
import { RuntimeBootstrap, runtimeCacheStorageKey, useRuntimeConfig } from './runtime-bootstrap'

class MemoryStorage implements Storage {
  readonly #values = new Map<string, string>()

  get length() {
    return this.#values.size
  }

  clear() {
    this.#values.clear()
  }

  getItem(key: string) {
    return this.#values.get(key) ?? null
  }

  key(index: number) {
    return [...this.#values.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.#values.delete(key)
  }

  setItem(key: string, value: string) {
    this.#values.set(key, value)
  }
}

class ThrowingStorage implements Storage {
  get length(): number {
    throw new DOMException('Denied', 'SecurityError')
  }

  clear(): void {
    // Cleanup remains harmless even if browser access methods are denied.
  }

  getItem(): string | null {
    throw new DOMException('Denied', 'SecurityError')
  }

  key(): string | null {
    throw new DOMException('Denied', 'SecurityError')
  }

  removeItem(): void {
    throw new DOMException('Denied', 'SecurityError')
  }

  setItem(): void {
    throw new DOMException('Denied', 'SecurityError')
  }
}

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: new MemoryStorage(),
  })
})

afterEach(() => {
  vi.useRealTimers()
  cleanup()
  window.localStorage.clear()
  document.documentElement.classList.remove('dark')
  document.documentElement.style.colorScheme = ''
})

function responseWith(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    status,
  })
}

function ProtectedRuntimeProbe() {
  const runtime = useRuntimeConfig()
  return <p>Открыт {runtime.audience}</p>
}

describe('RuntimeBootstrap', () => {
  it('shows a Russian loading state and mounts protected content only after validation', async () => {
    let resolveResponse: ((response: Response) => void) | undefined
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(
      () =>
        new Promise<Response>((resolve) => {
          resolveResponse = resolve
        }),
    )

    render(
      <RuntimeBootstrap audience="student" fetchImplementation={fetchImplementation}>
        {() => <ProtectedRuntimeProbe />}
      </RuntimeBootstrap>,
    )

    expect(screen.getByRole('status').textContent).toContain('Проверяем подключение')
    expect(screen.queryByText('Открыт student')).toBeNull()

    resolveResponse?.(responseWith(studentRuntimeFixture.response))
    expect(await screen.findByText('Открыт student')).not.toBeNull()
    expect(
      JSON.parse(window.localStorage.getItem(runtimeCacheStorageKey('student')) ?? 'null'),
    ).toEqual(studentRuntimeFixture.response)
  })

  it('uses only a previously validated same-audience runtime after a network failure', async () => {
    window.localStorage.setItem(
      runtimeCacheStorageKey('student'),
      JSON.stringify(studentRuntimeFixture.response),
    )
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.reject(new TypeError('Network unavailable')),
    )

    render(
      <RuntimeBootstrap audience="student" fetchImplementation={fetchImplementation}>
        {() => <ProtectedRuntimeProbe />}
      </RuntimeBootstrap>,
    )

    expect(await screen.findByText('Открыт student')).not.toBeNull()
  })

  it('does not use a cached runtime for an authoritative API rejection', async () => {
    window.localStorage.setItem(
      runtimeCacheStorageKey('student'),
      JSON.stringify(studentRuntimeFixture.response),
    )
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        responseWith(
          {
            error: {
              code: 'maintenance',
              message: 'Maintenance',
              requestId: 'request-maintenance',
            },
          },
          503,
        ),
      ),
    )

    render(
      <RuntimeBootstrap audience="student" fetchImplementation={fetchImplementation}>
        {() => <ProtectedRuntimeProbe />}
      </RuntimeBootstrap>,
    )

    expect(await screen.findByRole('alert')).not.toBeNull()
    expect(screen.queryByText('Открыт student')).toBeNull()
  })

  it('fails closed for a cross-audience payload and can retry without a fallback shell', async () => {
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        responseWith({
          ...studentRuntimeFixture.response,
          audience: 'family',
          appBase: '/family',
          apiBase: '/family/api/v1',
          websocketPath: '/family/ws',
        }),
      )
      .mockResolvedValueOnce(responseWith(studentRuntimeFixture.response))

    render(
      <RuntimeBootstrap audience="student" fetchImplementation={fetchImplementation}>
        {() => <ProtectedRuntimeProbe />}
      </RuntimeBootstrap>,
    )

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Не удалось безопасно открыть кабинет')
    expect(screen.queryByText('Открыт student')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText('Открыт student')).not.toBeNull()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('shows a correlation id from a validated API error without rendering server copy', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        responseWith(
          {
            error: {
              code: 'maintenance',
              message: 'Internal server detail must not become startup UI',
              requestId: 'request-visible-to-support',
            },
          },
          503,
        ),
      ),
    )

    render(
      <RuntimeBootstrap audience="student" fetchImplementation={fetchImplementation}>
        {() => <ProtectedRuntimeProbe />}
      </RuntimeBootstrap>,
    )

    expect(await screen.findByText('Код обращения: request-visible-to-support')).not.toBeNull()
    expect(screen.queryByText('Internal server detail must not become startup UI')).toBeNull()
  })

  it('turns a hung runtime request into a retryable error instead of loading forever', async () => {
    vi.useFakeTimers()
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError')),
        )
      })
    })

    render(
      <RuntimeBootstrap
        audience="student"
        fetchImplementation={fetchImplementation}
        timeoutMilliseconds={25}
      >
        {() => <ProtectedRuntimeProbe />}
      </RuntimeBootstrap>,
    )

    expect(screen.getByRole('status').textContent).toContain('Проверяем подключение')
    await act(() => vi.advanceTimersByTimeAsync(25))
    expect(screen.getByRole('alert').textContent).toContain('Не удалось безопасно открыть кабинет')
    expect(screen.queryByText('Открыт student')).toBeNull()
  })
})

describe('theme namespace', () => {
  it('reads and writes theme only below the full audience and instance namespace', async () => {
    const namespace = createBrowserStorageNamespace({ audience: 'student', instance: 'agent' })
    const otherNamespace = createBrowserStorageNamespace({ audience: 'student', instance: 'human' })
    window.localStorage.setItem(themeStorageKey(namespace), 'dark')
    window.localStorage.setItem(themeStorageKey(otherNamespace), 'light')

    render(
      <AppProviders storageNamespace={namespace}>
        <ThemeToggle />
      </AppProviders>,
    )

    await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Переключить на светлую тему' }))

    expect(window.localStorage.getItem(themeStorageKey(namespace))).toBe('light')
    expect(window.localStorage.getItem(themeStorageKey(otherNamespace))).toBe('light')
    expect(window.localStorage.getItem('vmsh-student-theme')).toBeNull()
  })

  it('does not accept an unnamespaced value at the type boundary', () => {
    const namespace = createBrowserStorageNamespace({ audience: 'staff', instance: 'e2e' })
    expect(themeStorageKey(namespace)).toBe(`${namespace}:theme`)
  })

  it('keeps the shell and in-memory theme usable when localStorage is denied', async () => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: new ThrowingStorage(),
    })
    const namespace = createBrowserStorageNamespace({ audience: 'staff', instance: 'agent' })

    render(
      <AppProviders storageNamespace={namespace}>
        <p>Кабинет открыт</p>
        <ThemeToggle />
      </AppProviders>,
    )

    expect(screen.getByText('Кабинет открыт')).not.toBeNull()
    const toggle = screen.getByRole('button', { name: /Переключить на/ })
    fireEvent.click(toggle)
    await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(true))
  })
})

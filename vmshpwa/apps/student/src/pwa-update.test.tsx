import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { AnyRouter } from '@tanstack/react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PwaUpdateController } from './pwa-update'
import { safePwaUpdateEvent } from './pwa-update-events'

const pwaMocks = vi.hoisted(() => ({
  updateServiceWorker: vi.fn<() => Promise<void>>(),
}))

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    needRefresh: [true, vi.fn()],
    offlineReady: [false, vi.fn()],
    updateServiceWorker: pwaMocks.updateServiceWorker,
  }),
}))

const originalServiceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
const originalOnLine = Object.getOwnPropertyDescriptor(navigator, 'onLine')

function routerStub(): AnyRouter {
  return {
    latestLocation: { href: '/student/tasks' },
    subscribe: vi.fn(() => () => undefined),
  } as unknown as AnyRouter
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  if (originalServiceWorker) {
    Object.defineProperty(navigator, 'serviceWorker', originalServiceWorker)
  } else {
    Reflect.deleteProperty(navigator, 'serviceWorker')
  }
  if (originalOnLine) Object.defineProperty(navigator, 'onLine', originalOnLine)
})

beforeEach(() => {
  pwaMocks.updateServiceWorker.mockReset()
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
})

describe('PWA update controller', () => {
  it('allows the button to retry after an automatic activation did not take control', async () => {
    const postMessage = vi.fn()
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: {
        addEventListener: vi.fn(),
        getRegistration: vi.fn().mockResolvedValue({ waiting: { postMessage } }),
        removeEventListener: vi.fn(),
      },
    })

    render(<PwaUpdateController router={routerStub()} />)

    fireEvent(window, new Event(safePwaUpdateEvent))
    await waitFor(() => expect(postMessage).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'Обновить сейчас' }))
    await waitFor(() => expect(postMessage).toHaveBeenCalledTimes(2))
  })

  it('allows a manual retry after the fallback updater fails', async () => {
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: {
        addEventListener: vi.fn(),
        getRegistration: vi.fn().mockResolvedValue({ waiting: null }),
        removeEventListener: vi.fn(),
      },
    })
    pwaMocks.updateServiceWorker.mockRejectedValueOnce(new Error('activation failed'))
    pwaMocks.updateServiceWorker.mockResolvedValueOnce(undefined)

    render(<PwaUpdateController router={routerStub()} />)

    fireEvent(window, new Event(safePwaUpdateEvent))
    await waitFor(() => expect(pwaMocks.updateServiceWorker).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'Обновить сейчас' }))
    await waitFor(() => expect(pwaMocks.updateServiceWorker).toHaveBeenCalledTimes(2))
  })
})

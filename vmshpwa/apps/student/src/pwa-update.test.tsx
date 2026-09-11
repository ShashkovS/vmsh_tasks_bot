import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { AnyRouter } from '@tanstack/react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PwaUpdateController } from './pwa-update'
import { safePwaUpdateEvent } from './pwa-update-events'

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    needRefresh: [true, vi.fn()],
    offlineReady: [false, vi.fn()],
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
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
})

describe('PWA update controller', () => {
  it('shows activation progress and lets the user retry after a message failure', async () => {
    const postMessage = vi.fn().mockImplementationOnce(() => {
      throw new Error('activation failed')
    })
    const worker = Object.assign(new EventTarget(), { state: 'installed', postMessage })
    const registration = Object.assign(new EventTarget(), {
      waiting: worker,
      active: null,
      installing: null,
    })
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: Object.assign(new EventTarget(), {
        getRegistration: vi.fn().mockResolvedValue(registration),
      }),
    })
    render(<PwaUpdateController router={routerStub()} />)
    fireEvent(window, new Event(safePwaUpdateEvent))
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain('Попробуйте ещё раз'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Обновить сейчас' }))
    await waitFor(() => expect(postMessage).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('button', { name: 'Обновляем…' }).hasAttribute('disabled')).toBe(true)
    fireEvent(window, new Event(safePwaUpdateEvent))
    expect(postMessage).toHaveBeenCalledTimes(2)
  })
})

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { NotificationClient } from './notification-client'
import { usePushDevice } from './push-device'

const originalServiceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')

function subscription() {
  return {
    endpoint: 'https://push.example.test/subscription',
    expirationTime: null,
    options: {} as PushSubscriptionOptions,
    getKey: vi.fn(),
    unsubscribe: vi.fn().mockResolvedValue(true),
    toJSON: () => ({
      endpoint: 'https://push.example.test/subscription',
      expirationTime: null,
      keys: { p256dh: 'a'.repeat(24), auth: 'b'.repeat(24) },
    }),
  } satisfies PushSubscription
}

function client() {
  const save = vi.fn().mockResolvedValue({})
  const remove = vi.fn().mockResolvedValue({})
  return {
    value: {
      savePushSubscription: save,
      deletePushSubscription: remove,
    } as unknown as NotificationClient,
    save,
    remove,
  }
}

function browser(registration: {
  pushManager: Pick<PushManager, 'getSubscription' | 'subscribe'>
}) {
  vi.stubGlobal('PushManager', class {})
  vi.stubGlobal('Notification', {
    permission: 'default',
    requestPermission: vi.fn().mockResolvedValue('granted'),
  })
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { ready: Promise.resolve(registration) },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  if (originalServiceWorker) {
    Object.defineProperty(navigator, 'serviceWorker', originalServiceWorker)
  } else {
    Reflect.deleteProperty(navigator, 'serviceWorker')
  }
})

describe('usePushDevice', () => {
  it('subscribes only after the contextual browser permission action', async () => {
    const saved = client()
    const created = subscription()
    const registration = {
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(null),
        subscribe: vi.fn().mockResolvedValue(created),
      },
    }
    browser(registration)
    const { result } = renderHook(() =>
      usePushDevice({ applicationServerKey: 'BA-_', client: saved.value }),
    )
    await waitFor(() => expect(result.current.state).toBe('available'))

    await act(() => result.current.enable())

    expect(registration.pushManager.subscribe).toHaveBeenCalledOnce()
    expect(saved.save).toHaveBeenCalledWith(expect.objectContaining({ endpoint: created.endpoint }))
    expect(result.current.state).toBe('enabled')
  })

  it('reconciles an existing subscription and removes it from server and browser', async () => {
    const saved = client()
    const existing = subscription()
    const registration = {
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(existing),
        subscribe: vi.fn(),
      },
    }
    browser(registration)
    const { result } = renderHook(() =>
      usePushDevice({ applicationServerKey: 'BA-_', client: saved.value }),
    )
    await waitFor(() => expect(result.current.state).toBe('enabled'))

    await act(() => result.current.disable())

    expect(saved.remove).toHaveBeenCalledWith(existing.endpoint)
    expect(existing.unsubscribe).toHaveBeenCalledOnce()
    expect(result.current.state).toBe('available')
  })
})

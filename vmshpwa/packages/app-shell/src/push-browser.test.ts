import { describe, expect, it, vi } from 'vitest'

import { browserPushSubscriptionRequest, decodeApplicationServerKey } from './push-browser'

describe('browser push helpers', () => {
  it('decodes an unpadded URL-safe application server key', () => {
    expect([...decodeApplicationServerKey('BA-_')]).toEqual([4, 15, 191])
  })

  it('serializes the browser-owned subscription without extra fields', () => {
    const p256dh = `B${'a'.repeat(86)}`
    const auth = 'b'.repeat(22)
    const subscription = {
      toJSON: vi.fn(() => ({
        endpoint: 'https://push.example.test/device-one',
        expirationTime: null,
        keys: { p256dh, auth },
      })),
    } as unknown as PushSubscription

    expect(browserPushSubscriptionRequest(subscription)).toEqual({
      schemaVersion: 1,
      endpoint: 'https://push.example.test/device-one',
      expirationTime: null,
      keys: { p256dh, auth },
    })
  })
})

import { describe, expect, it, vi } from 'vitest'

import eventsFixture from '@vmsh/contracts/fixtures/notifications/events.v1.json'
import preferencesFixture from '@vmsh/contracts/fixtures/notifications/preferences.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createNotificationClient } from './notification-client'

const runtime = runtimeConfigSchemaForAudience('student').parse(runtimeFixture.response)

describe('notification client', () => {
  it('uses the audience API and validates list responses', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(eventsFixture))
      .mockResolvedValueOnce(Response.json(preferencesFixture))
    const client = createNotificationClient(runtime, 'student', { fetchImplementation })

    expect((await client.events({ unreadOnly: true })).items[0]?.category).toBe(
      'classroom_assignment',
    )
    expect((await client.preferences()).items).toHaveLength(9)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/student/api/v1/notification-events?limit=50&unreadOnly=true',
    )
  })

  it('sends validated preference and read mutations', async () => {
    const preference = preferencesFixture.items.find((item) => item.category === 'news')!
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          preference: { ...preference, pushEnabled: false },
          requestId: 'request-update',
        }),
      )
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          eventId: 'notification.classroom-41',
          readAt: '2026-10-05T12:00:03Z',
          requestId: 'request-read',
        }),
      )
    const client = createNotificationClient(runtime, 'student', { fetchImplementation })

    await client.updatePreference({
      schemaVersion: 1,
      category: 'news',
      inAppEnabled: true,
      pushEnabled: false,
      soundEnabled: true,
      quietStartsLocal: '21:00',
      quietEndsLocal: '09:00',
      timezone: 'Europe/Moscow',
    })
    await client.acknowledge('notification.classroom-41')

    expect(fetchImplementation.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ method: 'PUT', credentials: 'include' }),
    )
    expect(fetchImplementation.mock.calls[1]?.[0]).toContain('/notification-events/')
  })

  it('refreshes once after a 401', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(Response.json(eventsFixture))
    const refreshSession = vi.fn(() => Promise.resolve())

    await createNotificationClient(runtime, 'student', {
      fetchImplementation,
      refreshSession,
    }).events()

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('registers and removes the current browser push endpoint', async () => {
    const p256dh = `B${'a'.repeat(86)}`
    const auth = 'b'.repeat(22)
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          enabled: true,
          applicationServerKey: p256dh,
          requestId: 'request-config',
        }),
      )
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          subscriptionId: 'push.device-one',
          requestId: 'request-save',
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, deleted: true, requestId: 'request-delete' }),
      )
    const client = createNotificationClient(runtime, 'student', { fetchImplementation })
    const endpoint = 'https://push.example.test/device-one'

    expect((await client.pushConfig()).enabled).toBe(true)
    await client.savePushSubscription({
      schemaVersion: 1,
      endpoint,
      expirationTime: null,
      keys: { p256dh, auth },
    })
    expect((await client.deletePushSubscription(endpoint)).deleted).toBe(true)

    expect(fetchImplementation.mock.calls.map((call) => call[1]?.method)).toEqual([
      'GET',
      'POST',
      'DELETE',
    ])
  })
})

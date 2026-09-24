import { describe, expect, it, vi } from 'vitest'

import { createStaffOralWindowClient } from './staff-oral-window-client'

const runtime = {
  contractVersion: 1 as const,
  audience: 'staff' as const,
  appBase: '/staff',
  apiBase: '/staff/api/v1',
  websocketPath: '/staff/ws',
  instance: 'test',
  serverTime: '2026-10-05T12:00:00Z',
  requestId: 'runtime.1',
  features: { telegram: false, google: false, nats: false, prototype: false },
}

const input = {
  schemaVersion: 1 as const,
  sequenceNumber: 2,
  opensAt: '2026-10-07T15:00:00Z',
  closesAt: '2026-10-07T17:00:00Z',
  joinLabel: 'Подключиться',
  joinUrl: 'https://zoom.example.test/j/179',
  joinCode: null,
  status: 'active' as const,
}

describe('Staff oral-window client', () => {
  it('sends create and versioned update directly to their endpoints', async () => {
    const window = {
      windowId: 'oral-window.2',
      sequenceNumber: 2,
      opensAt: input.opensAt,
      closesAt: input.closesAt,
      joinLabel: input.joinLabel,
      state: 'upcoming',
      joinAvailable: false,
      version: 3,
      joinUrl: input.joinUrl,
      joinCode: null,
      status: 'active',
    }
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ schemaVersion: 1, window, requestId: 'request.1' }), {
          status: 200,
        }),
      ),
    )
    const client = createStaffOralWindowClient(runtime, { fetchImplementation })

    await client.create('lesson.41', input)
    await client.update('oral-window.2', 3, input)

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/staff/api/v1/group-lessons/lesson.41/oral-windows',
    )
    expect(fetchImplementation.mock.calls[1]?.[1]?.headers).toEqual({
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'If-Match': '"oral-window.2:v3"',
    })
  })
})

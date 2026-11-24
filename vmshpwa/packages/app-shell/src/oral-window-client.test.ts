import { describe, expect, it, vi } from 'vitest'

import { createStudentOralWindowClient } from './oral-window-client'

const runtime = {
  contractVersion: 1 as const,
  audience: 'student' as const,
  appBase: '/student',
  apiBase: '/student/api/v1',
  websocketPath: '/student/ws',
  instance: 'test',
  serverTime: '2026-10-05T12:00:00Z',
  requestId: 'runtime.1',
  features: { telegram: false, google: false, nats: false, prototype: false },
}

describe('Student oral-window client', () => {
  it('uses the scoped list and separate join endpoints', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ schemaVersion: 1, items: [], requestId: 'request.list' }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schemaVersion: 1,
            join: {
              windowId: 'oral-window.1',
              joinLabel: 'Подключиться',
              joinUrl: 'https://zoom.example.test/j/179',
              joinCode: null,
              closesAt: '2026-10-05T13:00:00Z',
            },
            requestId: 'request.join',
          }),
          { status: 200 },
        ),
      )
    const client = createStudentOralWindowClient(runtime, { fetchImplementation })

    await client.list('course.math', 'lesson.41')
    await client.join('course.math', 'lesson.41', 'oral-window.1')

    expect(fetchImplementation.mock.calls.map(([url]) => url)).toEqual([
      '/student/api/v1/courses/course.math/lessons/lesson.41/oral-windows',
      '/student/api/v1/courses/course.math/lessons/lesson.41/oral-windows/oral-window.1/join',
    ])
  })
})

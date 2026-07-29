import { describe, expect, it, vi } from 'vitest'

import type { RuntimeConfig } from '@vmsh/contracts'

import { createFamilyCourseClient } from './family-course-client'

const runtime: RuntimeConfig = {
  contractVersion: 1,
  audience: 'family',
  appBase: '/family',
  apiBase: '/family/api/v1',
  websocketPath: '/family/ws',
  instance: 'unit',
  serverTime: '2026-07-29T12:00:00Z',
  requestId: 'request-family-course',
  features: { telegram: false, google: false, nats: false, prototype: false },
}

const payload = {
  student: {
    studentId: 'student.one',
    displayName: 'Анна Петрова',
    grade: null,
    birthday: null,
    relationshipLabel: null,
    isPrimary: true,
  },
  enrollments: [],
}

describe('Family course client', () => {
  it('uses the Family boundary and validates the response', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const client = createFamilyCourseClient(runtime, { fetchImplementation })

    await expect(client.childCourses('student.one')).resolves.toEqual(payload)
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/family/api/v1/children/student.one/courses',
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )
  })

  it('refreshes once after an expired access cookie', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    const refreshSession = vi.fn().mockResolvedValue(undefined)
    const client = createFamilyCourseClient(runtime, { fetchImplementation, refreshSession })

    await client.childCourses('student.one')
    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('rejects an unsafe child ID before the network', async () => {
    const fetchImplementation = vi.fn<typeof fetch>()
    const client = createFamilyCourseClient(runtime, { fetchImplementation })
    await expect(client.childCourses('../other')).rejects.toThrow()
    expect(fetchImplementation).not.toHaveBeenCalled()
  })
})

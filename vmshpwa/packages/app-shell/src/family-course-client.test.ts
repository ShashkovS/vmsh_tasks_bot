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

  it('loads the selected child home from its own route', async () => {
    const home = { student: payload.student, courses: [] }
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(home), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const client = createFamilyCourseClient(runtime, { fetchImplementation })
    await expect(client.childHome('student.one')).resolves.toEqual(home)
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/family/api/v1/children/student.one/home',
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )
  })

  it('updates one course enrollment through the Family boundary', async () => {
    const enrollment = {
      enrollmentId: 'enrollment.one',
      studentId: 'student.one',
      course: {
        courseId: 'course.math',
        code: 'math',
        name: 'Математика',
        subjectCode: 'math',
        status: 'active',
        sortOrder: 1,
        accentKey: 'math',
        version: 1,
      },
      activeGroupId: 'group.b',
      allowedGroups: [
        {
          groupId: 'group.b',
          courseId: 'course.math',
          code: 'b',
          name: 'B',
          status: 'active',
          sortOrder: 2,
          colorKey: 'level-2',
          version: 1,
        },
      ],
      attendanceMode: 'in_person',
      status: 'active',
      version: 2,
    }
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(enrollment), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const client = createFamilyCourseClient(runtime, { fetchImplementation })

    await expect(
      client.updateEnrollment('student.one', 'course.math', {
        activeGroupId: 'group.b',
        attendanceMode: 'in_person',
        version: 1,
      }),
    ).resolves.toEqual(enrollment)
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/family/api/v1/children/student.one/courses/course.math/enrollment',
      expect.objectContaining({
        credentials: 'include',
        method: 'PATCH',
        body: JSON.stringify({
          activeGroupId: 'group.b',
          attendanceMode: 'in_person',
          version: 1,
        }),
      }),
    )
  })
})

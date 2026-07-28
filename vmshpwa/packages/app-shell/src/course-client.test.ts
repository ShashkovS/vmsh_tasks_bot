import { describe, expect, it, vi } from 'vitest'

import studentAccessFixture from '../../contracts/fixtures/courses/student-access.v1.json'
import studentHomeFixture from '../../contracts/fixtures/courses/student-home.v1.json'
import studentLessonsFixture from '../../contracts/fixtures/courses/student-lessons.v1.json'
import { runtimeBoundaryByAudience, type RuntimeConfig } from '@vmsh/contracts'

import { CourseProtocolError, createStudentCourseClient } from './course-client'

function runtime(audience: RuntimeConfig['audience'] = 'student'): RuntimeConfig {
  const boundary = runtimeBoundaryByAudience[audience]
  return {
    contractVersion: 1,
    audience,
    appBase: boundary.appBase,
    apiBase: boundary.apiBase,
    websocketPath: boundary.websocketPath,
    instance: 'course-client-test',
    serverTime: '2026-07-28T00:00:00Z',
    requestId: 'course-client-test',
    features: { telegram: false, google: false, nats: false, prototype: false },
  }
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Phase-3 Student course client', () => {
  it('reads the complete multi-course home through one request', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(studentHomeFixture.response)),
    )
    const client = createStudentCourseClient(runtime(), { fetchImplementation })

    await expect(client.home()).resolves.toEqual(studentHomeFixture.response)
    expect(fetchImplementation).toHaveBeenCalledOnce()
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/student/api/v1/home')
  })

  it('reads and validates the course list through the Student API base', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(studentAccessFixture.response)),
    )
    const client = createStudentCourseClient(runtime(), { fetchImplementation })

    await expect(client.list()).resolves.toEqual(studentAccessFixture.response)
    expect(fetchImplementation).toHaveBeenCalledOnce()
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/student/api/v1/courses')
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'GET',
      cache: 'no-store',
      credentials: 'include',
      redirect: 'error',
    })
  })

  it('loads exactly one validated enrollment', async () => {
    const enrollment = studentAccessFixture.response.enrollments[0]!
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(enrollment)),
    )
    const client = createStudentCourseClient(runtime(), { fetchImplementation })

    await expect(client.enrollment(enrollment.course.courseId)).resolves.toEqual(enrollment)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      `/student/api/v1/courses/${enrollment.course.courseId}/enrollment`,
    )
  })

  it('loads a validated lesson page for an explicit allowed group', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(studentLessonsFixture.response)),
    )
    const client = createStudentCourseClient(runtime(), { fetchImplementation })

    await expect(
      client.lessons('course-fixture-alpha', {
        groupId: 'group-fixture-alpha-one',
        cursor: '43',
      }),
    ).resolves.toEqual(studentLessonsFixture.response)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/student/api/v1/courses/course-fixture-alpha/lessons?group=group-fixture-alpha-one&cursor=43',
    )
  })

  it('loads one concrete group lesson without weakening its provenance', async () => {
    const lesson = studentLessonsFixture.response.lessons[0]!
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(lesson)),
    )
    const client = createStudentCourseClient(runtime(), { fetchImplementation })

    await expect(client.lesson(lesson.courseId, lesson.groupLessonId)).resolves.toEqual(lesson)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      `/student/api/v1/courses/${lesson.courseId}/lessons/${lesson.groupLessonId}`,
    )
  })

  it('refreshes once after 401 and retries the same bounded read', async () => {
    const refreshSession = vi.fn(() => Promise.resolve())
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'authentication_required',
              message: 'Войдите',
              requestId: 'course-client-401',
            },
          },
          401,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(studentAccessFixture.response))
    const client = createStudentCourseClient(runtime(), {
      fetchImplementation,
      refreshSession,
    })

    await expect(client.list()).resolves.toEqual(studentAccessFixture.response)
    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('rejects invalid resource IDs before sending a request', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse({})),
    )
    const client = createStudentCourseClient(runtime(), { fetchImplementation })

    await expect(client.enrollment('../another-course')).rejects.toThrow()
    await expect(
      client.lessons('course-fixture-alpha', { cursor: '../unsafe-cursor' }),
    ).rejects.toThrow()
    await expect(client.lesson('course-fixture-alpha', '../unsafe-lesson')).rejects.toThrow()
    expect(fetchImplementation).not.toHaveBeenCalled()
  })

  it('fails closed on another audience and malformed successful payloads', async () => {
    expect(() => createStudentCourseClient(runtime('family'))).toThrow()

    const client = createStudentCourseClient(runtime(), {
      fetchImplementation: () =>
        Promise.resolve(jsonResponse({ studentId: 'wrong', enrollments: [{}] })),
    })
    await expect(client.list()).rejects.toBeInstanceOf(CourseProtocolError)
  })
})

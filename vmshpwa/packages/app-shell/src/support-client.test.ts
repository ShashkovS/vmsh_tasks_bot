import { runtimeConfigSchema } from '@vmsh/contracts'
import { describe, expect, it, vi } from 'vitest'

import { createSupportClient } from './support-client'

const studentRuntime = runtimeConfigSchema.parse({
  contractVersion: 1,
  audience: 'student',
  appBase: '/student',
  apiBase: '/student/api/v1',
  websocketPath: '/student/ws',
  instance: 'support-client-test',
  serverTime: '2026-10-05T12:00:00Z',
  requestId: 'runtime-request',
  features: { telegram: false, google: false, nats: false, prototype: false },
})

const staffRuntime = runtimeConfigSchema.parse({
  ...studentRuntime,
  audience: 'staff',
  appBase: '/staff',
  apiBase: '/staff/api/v1',
  websocketPath: '/staff/ws',
})

const response = {
  schemaVersion: 1 as const,
  thread: {
    threadId: 'support-thread-one',
    kind: 'general' as const,
    student: { studentId: 'student-one', displayName: 'Анна Белова' },
    context: {
      courseId: 'course-math',
      courseName: 'Математика',
      groupId: 'group-a',
      groupName: 'Начинающие',
      groupLessonId: 'group-lesson-41',
      problemId: null,
      problemTitle: null,
    },
    latestEntryAt: '2026-10-05T12:00:00.000000Z',
    version: 1,
    entries: [
      {
        entryId: 'support-entry-one',
        author: { kind: 'student' as const, userId: 'student-one', displayName: 'Анна Белова' },
        text: 'Когда следующий разбор?',
        assetId: null,
        channel: 'pwa' as const,
        clientCreatedAt: '2026-10-05T11:59:00.000000Z',
        receivedAt: '2026-10-05T12:00:00.000000Z',
      },
    ],
  },
  requestId: 'support-response',
}

const pageResponse = {
  schemaVersion: 1 as const,
  items: [
    {
      threadId: response.thread.threadId,
      kind: response.thread.kind,
      student: response.thread.student,
      context: response.thread.context,
      latestEntry: {
        authorKind: 'student' as const,
        textExcerpt: 'Когда следующий разбор?',
        receivedAt: response.thread.latestEntryAt,
      },
      replyState: 'awaiting_staff' as const,
      entryCount: 1,
      version: 1,
    },
  ],
  nextCursor: null,
  requestId: 'support-list-response',
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('support client', () => {
  it('uses audience API base and serializes strict create/append payloads', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(response)),
    )
    const client = createSupportClient(studentRuntime, { fetchImplementation })
    await client.create({
      schemaVersion: 1,
      idempotencyKey: 'support-create-one',
      kind: 'general',
      groupLessonId: 'group-lesson-41',
      problemId: null,
      text: 'Когда следующий разбор?',
      clientCreatedAt: '2026-10-05T11:59:00Z',
    })
    await client.get('support-thread-one')
    await client.append('support-thread-one', {
      schemaVersion: 1,
      idempotencyKey: 'support-append-one',
      text: 'Спасибо!',
      clientCreatedAt: '2026-10-05T12:01:00Z',
    })

    expect(fetchImplementation.mock.calls.map(([path]) => path)).toEqual([
      '/student/api/v1/questions',
      '/student/api/v1/questions/support-thread-one',
      '/student/api/v1/questions/support-thread-one/entries',
    ])
    expect(fetchImplementation.mock.calls.map(([, init]) => init?.method)).toEqual([
      'POST',
      'GET',
      'POST',
    ])
  })

  it('rejects Family construction and malformed server payloads', async () => {
    expect(() =>
      createSupportClient({
        ...studentRuntime,
        audience: 'family',
        appBase: '/family',
        apiBase: '/family/api/v1',
        websocketPath: '/family/ws',
      }),
    ).toThrow('Family')
    const client = createSupportClient(studentRuntime, {
      fetchImplementation: () => Promise.resolve(jsonResponse({ schemaVersion: 1 })),
    })
    await expect(client.get('support-thread-one')).rejects.toThrow('contract validation')
  })

  it('serializes Student history and Staff inbox filters independently', async () => {
    const studentFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(pageResponse)),
    )
    const staffFetch = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(pageResponse)),
    )
    const student = createSupportClient(studentRuntime, { fetchImplementation: studentFetch })
    const staff = createSupportClient(staffRuntime, { fetchImplementation: staffFetch })

    await student.listStudent({ cursor: 'support-thread-before' })
    await staff.listStaff({
      state: 'awaiting_student',
      kind: 'general',
      courseId: 'course-math',
      groupId: 'group-a',
      cursor: 'support-thread-before',
    })

    expect(studentFetch.mock.calls[0]?.[0]).toBe(
      '/student/api/v1/questions?cursor=support-thread-before',
    )
    expect(staffFetch.mock.calls[0]?.[0]).toBe(
      '/staff/api/v1/questions?state=awaiting_student&kind=general&course=course-math&group=group-a&cursor=support-thread-before',
    )
    await expect(student.listStaff()).rejects.toThrow('Only Staff')
    await expect(staff.listStudent()).rejects.toThrow('Only Student')
  })
})

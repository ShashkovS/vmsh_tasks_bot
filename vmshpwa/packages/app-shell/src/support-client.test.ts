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
})

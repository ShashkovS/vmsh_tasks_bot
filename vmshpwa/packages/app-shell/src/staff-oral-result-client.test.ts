import { describe, expect, it, vi } from 'vitest'

import type { RuntimeConfig } from '@vmsh/contracts'

import { createStaffOralResultClient } from './staff-oral-result-client'

const runtime: RuntimeConfig = {
  contractVersion: 1,
  audience: 'staff',
  appBase: '/staff',
  apiBase: '/staff/api/v1',
  websocketPath: '/staff/ws',
  instance: 'test',
  serverTime: '2026-07-29T12:00:00Z',
  requestId: 'runtime.1',
  features: { telegram: false, google: false, nats: false, prototype: false },
}

describe('Staff oral result client', () => {
  it('loads the roster and records one round', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schemaVersion: 1,
            groupLessonId: 'lesson.41',
            students: [{ studentId: 'student.1', displayName: 'Анна Белова' }],
            problems: [{ problemId: 'problem.1', displayNumber: '1', title: 'Ладьи' }],
            requestId: 'request.1',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schemaVersion: 1,
            idempotencyKey: 'oral-round.1',
            replayed: false,
            marks: [{ problemId: 'problem.1', outcome: 'accepted' }],
            reactionId: 300,
            requestId: 'request.2',
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } },
        ),
      )
    const client = createStaffOralResultClient(runtime, { fetchImplementation })

    await client.roster('lesson.41')
    await client.record('lesson.41', {
      schemaVersion: 1,
      studentId: 'student.1',
      idempotencyKey: 'oral-round.1',
      marks: [{ problemId: 'problem.1', outcome: 'accepted' }],
      reactionId: 300,
    })

    expect(fetchImplementation.mock.calls.map(([url]) => url)).toEqual([
      '/staff/api/v1/group-lessons/lesson.41/oral-roster',
      '/staff/api/v1/group-lessons/lesson.41/oral-results',
    ])
  })
})

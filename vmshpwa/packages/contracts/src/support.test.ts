import { describe, expect, it } from 'vitest'

import {
  createSupportThreadRequestSchema,
  staffSupportListQuerySchema,
  supportQueryKeys,
  supportThreadPageSchema,
  supportThreadResponseSchema,
} from './support'

const response = {
  schemaVersion: 1,
  thread: {
    threadId: 'support-thread-one',
    kind: 'problem_question',
    student: { studentId: 'student-one', displayName: 'Анна Белова' },
    context: {
      courseId: 'course-math',
      courseName: 'Математика',
      groupId: 'group-a',
      groupName: 'Начинающие',
      groupLessonId: 'group-lesson-41',
      problemId: 'problem-one',
      problemTitle: 'Перестановки',
    },
    latestEntryAt: '2026-10-05T12:01:00.000000Z',
    version: 2,
    entries: [
      {
        entryId: 'support-entry-one',
        author: { kind: 'student', userId: 'student-one', displayName: 'Анна Белова' },
        text: 'Почему эти случаи одинаковые?',
        assetId: null,
        channel: 'pwa',
        clientCreatedAt: '2026-10-05T12:00:00.000000Z',
        receivedAt: '2026-10-05T12:00:00.000000Z',
      },
      {
        entryId: 'support-entry-two',
        author: { kind: 'teacher', userId: 'teacher-one', displayName: 'Мария Учитель' },
        text: 'Посмотрите на перестановку двух случаев.',
        assetId: null,
        channel: 'staff',
        clientCreatedAt: '2026-10-05T12:01:00.000000Z',
        receivedAt: '2026-10-05T12:01:00.000000Z',
      },
    ],
  },
  requestId: 'support-contract-test',
}

describe('support contracts', () => {
  it('accepts one complete chronological private thread', () => {
    expect(supportThreadResponseSchema.parse(response)).toEqual(response)
  })

  it('rejects inconsistent target kinds, chronology and latest timestamp', () => {
    expect(() =>
      createSupportThreadRequestSchema.parse({
        schemaVersion: 1,
        idempotencyKey: 'support-create',
        kind: 'general',
        groupLessonId: 'group-lesson-41',
        problemId: 'problem-one',
        text: 'Общий вопрос',
        clientCreatedAt: '2026-10-05T12:00:00Z',
      }),
    ).toThrow()
    expect(() =>
      supportThreadResponseSchema.parse({
        ...response,
        thread: {
          ...response.thread,
          latestEntryAt: '2026-10-05T12:00:00.000000Z',
          entries: [...response.thread.entries].reverse(),
        },
      }),
    ).toThrow()
  })

  it('isolates query keys by audience and account', () => {
    expect(
      supportQueryKeys.thread(
        { audience: 'student', accountId: 'account-student' },
        'support-thread-one',
      ),
    ).not.toEqual(
      supportQueryKeys.thread(
        { audience: 'staff', accountId: 'account-teacher' },
        'support-thread-one',
      ),
    )
  })

  it('validates inbox derivation and strict list filters', () => {
    expect(
      supportThreadPageSchema.parse({
        schemaVersion: 1,
        items: [
          {
            threadId: response.thread.threadId,
            kind: response.thread.kind,
            student: response.thread.student,
            context: response.thread.context,
            latestEntry: {
              authorKind: 'student',
              textExcerpt: 'Почему эти случаи одинаковые?',
              receivedAt: response.thread.latestEntryAt,
            },
            replyState: 'awaiting_staff',
            entryCount: 2,
            version: response.thread.version,
          },
        ],
        nextCursor: null,
        requestId: 'support-list-test',
      }).items[0]?.replyState,
    ).toBe('awaiting_staff')
    expect(() =>
      supportThreadPageSchema.parse({
        schemaVersion: 1,
        items: [
          {
            threadId: response.thread.threadId,
            kind: response.thread.kind,
            student: response.thread.student,
            context: response.thread.context,
            latestEntry: {
              authorKind: 'student',
              textExcerpt: null,
              receivedAt: response.thread.latestEntryAt,
            },
            replyState: 'awaiting_student',
            entryCount: 1,
            version: 1,
          },
        ],
        nextCursor: null,
        requestId: 'support-list-invalid',
      }),
    ).toThrow()
    expect(staffSupportListQuerySchema.parse({})).toEqual({ state: 'awaiting_staff' })
    expect(() => staffSupportListQuerySchema.parse({ unexpected: true })).toThrow()
  })

  it('includes normalized Staff filters and cursor in list cache identity', () => {
    const principal = { audience: 'staff' as const, accountId: 'account-teacher' }
    expect(supportQueryKeys.staffList(principal)).not.toEqual(
      supportQueryKeys.staffList(principal, {
        state: 'all',
        kind: 'general',
        courseId: 'course-math',
        groupId: 'group-a',
        cursor: 'support-thread-one',
      }),
    )
  })
})

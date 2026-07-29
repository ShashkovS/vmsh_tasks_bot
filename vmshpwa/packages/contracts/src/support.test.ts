import { describe, expect, it } from 'vitest'

import {
  createSupportThreadRequestSchema,
  supportQueryKeys,
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
})

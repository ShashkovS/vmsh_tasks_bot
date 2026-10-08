import { describe, expect, it } from 'vitest'

import {
  correctWrittenReviewRequestSchema,
  correctWrittenReviewResponseSchema,
  reviewReactionInboxQuerySchema,
  reviewReactionInboxResponseSchema,
} from './review-reactions'

const baseItem = {
  itemId: 'review-reaction-one',
  reviewId: 'review-one',
  kind: 'student' as const,
  reactionId: 2 as const,
  reactionLabel: '🙋 Не могу согласиться с проверкой!',
  reactionVersion: 1,
  updatedAt: '2026-07-29T10:10:00.000Z',
  editableUntil: '2026-07-29T11:00:00.000Z',
  student: { studentId: 'student-one', displayName: 'Анна Белова' },
  reviewer: { staffId: 'teacher-one', displayName: 'Ирина Соколова' },
  problem: {
    problemId: 'problem-one',
    problemNumber: '41n.6',
    problemTitle: 'Орехи и оценки',
    courseId: 'course-math',
    courseName: 'Математика 5–7',
    groupId: 'group-n',
    groupName: 'Начинающие',
    groupShortCode: 'n',
    groupColorKey: 'level-1',
  },
  verdict: 15,
  comment: 'Нужно обосновать последний переход.',
  completedAt: '2026-07-29T10:00:00.000Z',
  isLatestReview: true,
  evidenceEntries: [
    {
      entryId: 'submission-one',
      entryVersion: 1,
      entryKind: 'submission' as const,
      text: 'Решение ученика.',
      submittedAt: '2026-07-29T09:45:00.000Z',
      attachments: [],
    },
  ],
}

it('requires coherent optimistic correction expectations', () => {
  const legacy = {
    schemaVersion: 1,
    idempotencyKey: 'correction-one',
    verdict: 17,
    comment: null,
    confirmWithoutComment: false,
  }
  expect(correctWrittenReviewRequestSchema.safeParse(legacy).success).toBe(true)
  expect(correctWrittenReviewRequestSchema.safeParse({ ...legacy, annotations: [] }).success).toBe(
    false,
  )
  expect(
    correctWrittenReviewRequestSchema.safeParse({
      ...legacy,
      annotations: [],
      expectedLatestReviewId: 'r-1',
      expectedThreadVersion: 2,
      confirmReplaceNewer: false,
    }).success,
  ).toBe(true)
})

describe('admin review-reaction inbox contracts', () => {
  it('accepts exact Student and Teacher reaction rows', () => {
    const parsed = reviewReactionInboxResponseSchema.parse({
      schemaVersion: 1,
      items: [
        baseItem,
        {
          ...baseItem,
          itemId: 'review-reaction-two',
          kind: 'teacher',
          reactionId: 103,
          reactionLabel: '🤖 Решение, вероятно, от нейросети.',
        },
      ],
      nextCursor: null,
      requestId: 'reaction-inbox-test',
    })
    expect(parsed.items.map((item) => item.reactionId)).toEqual([2, 103])
  })

  it('rejects cross-kind IDs, stale timestamps and extra fields', () => {
    expect(
      reviewReactionInboxResponseSchema.safeParse({
        schemaVersion: 1,
        items: [{ ...baseItem, reactionId: 103 }],
        nextCursor: null,
        requestId: 'reaction-inbox-test',
      }).success,
    ).toBe(false)
    expect(
      reviewReactionInboxResponseSchema.safeParse({
        schemaVersion: 1,
        items: [
          {
            ...baseItem,
            updatedAt: '2026-07-29T12:00:00.000Z',
            unexpected: true,
          },
        ],
        nextCursor: null,
        requestId: 'reaction-inbox-test',
      }).success,
    ).toBe(false)
  })

  it('validates kind-aware filters', () => {
    expect(reviewReactionInboxQuerySchema.parse({ kind: 'student', reactionId: 2 })).toEqual({
      kind: 'student',
      reactionId: 2,
    })
    expect(
      reviewReactionInboxQuerySchema.safeParse({ kind: 'student', reactionId: 103 }).success,
    ).toBe(false)
    expect(
      reviewReactionInboxQuerySchema.safeParse({ kind: 'teacher', reactionId: 2 }).success,
    ).toBe(false)
  })

  it('validates the append-only correction command and receipt', () => {
    expect(
      correctWrittenReviewRequestSchema.parse({
        schemaVersion: 1,
        idempotencyKey: 'review-correction-one',
        verdict: 13,
        comment: 'Переход не доказан.',
        confirmWithoutComment: false,
      }).verdict,
    ).toBe(13)
    expect(
      correctWrittenReviewResponseSchema.parse({
        schemaVersion: 1,
        correction: {
          reviewId: 'review-corrected',
          correctsReviewId: 'review-one',
          threadId: 'thread-one',
          problemId: 'problem-one',
          verdict: 13,
          threadStatus: 'needs_work',
          completedAt: '2026-07-29T10:20:00.000Z',
          replayed: false,
        },
        requestId: 'review-correction-request',
      }).correction.correctsReviewId,
    ).toBe('review-one')
  })
})

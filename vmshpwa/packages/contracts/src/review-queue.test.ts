import { describe, expect, it } from 'vitest'

import {
  claimReviewItemRequestSchema,
  completeReviewRequestSchema,
  completeReviewResponseSchema,
  mutateReviewLeaseRequestSchema,
  releaseReviewLeaseResponseSchema,
  reviewLeaseResponseSchema,
  reviewQueueListResponseSchema,
  reviewQueueQueryKeys,
} from './review-queue'

const branches = [
  {
    queueId: 'review-queue-one',
    problemId: 'problem-one',
    problemTitle: 'Общая задача',
    courseId: 'course-math',
    groupId: 'group-a',
    submittedAt: '2026-10-04T12:01:00.000000Z',
    leaseVersion: 0,
  },
  {
    queueId: 'review-queue-two',
    problemId: 'problem-two',
    problemTitle: 'Общая задача',
    courseId: 'course-math',
    groupId: 'group-b',
    submittedAt: '2026-10-04T12:02:00.000000Z',
    leaseVersion: 0,
  },
]
const firstBranch = branches[0]!
const evidenceBranches = branches.map((branch, index) => ({
  queueId: branch.queueId,
  thread: {
    threadId: `thread-${index + 1}`,
    threadVersion: 2,
    entries: [
      {
        entryId: `entry-${index + 1}`,
        entryVersion: 2,
        entryKind: 'submission' as const,
        text: `Решение ${index + 1}`,
        submittedAt: branch.submittedAt,
        attachments: [],
      },
    ],
  },
}))

describe('Phase-6 review queue contracts', () => {
  const principal = { audience: 'staff' as const, accountId: 'staff-reviewer' }

  it('accepts one chronological synonym case without integer identities', () => {
    const payload = {
      schemaVersion: 1 as const,
      items: [
        {
          queueId: firstBranch.queueId,
          logicalCaseId: 'synonym-shared',
          student: { studentId: 'student-one', displayName: 'Анна Белова' },
          submittedAt: firstBranch.submittedAt,
          branches,
          lock: null,
        },
      ],
      nextCursor: null,
      requestId: 'request-review-list',
    }
    expect(reviewQueueListResponseSchema.parse(payload)).toEqual(payload)
  })

  it('rejects client identity, a mismatched anchor and hidden wire fields', () => {
    expect(
      claimReviewItemRequestSchema.safeParse({ schemaVersion: 1, teacherUserId: 42 }).success,
    ).toBe(false)
    expect(
      reviewQueueListResponseSchema.safeParse({
        schemaVersion: 1,
        items: [
          {
            queueId: 'review-queue-two',
            logicalCaseId: 'synonym-shared',
            student: { studentId: 'student-one', displayName: 'Анна Белова' },
            submittedAt: firstBranch.submittedAt,
            branches,
            lock: null,
          },
        ],
        nextCursor: null,
        requestId: 'request-review-list',
      }).success,
    ).toBe(false)
    expect(
      mutateReviewLeaseRequestSchema.safeParse({
        schemaVersion: 1,
        claimToken: 'review-claim-one',
        queueId: 'server-path-owned',
      }).success,
    ).toBe(false)
  })

  it('validates renewable leases and release receipts', () => {
    const leaseResponse = {
      schemaVersion: 1 as const,
      lease: {
        claimToken: 'review-claim-one',
        logicalCaseId: 'synonym-shared',
        student: { studentId: 'student-one', displayName: 'Анна Белова' },
        claimedAt: '2026-10-04T12:05:00.000000Z',
        expiresAt: '2026-10-04T12:35:00.000000Z',
        branches: branches.map((branch) => ({ ...branch, leaseVersion: 1 })),
        evidenceBranches,
      },
      requestId: 'request-review-claim',
    }
    expect(reviewLeaseResponseSchema.parse(leaseResponse)).toEqual(leaseResponse)
    expect(
      releaseReviewLeaseResponseSchema.parse({
        schemaVersion: 1,
        releasedItems: 2,
        requestId: 'request-review-release',
      }).releasedItems,
    ).toBe(2)
  })

  it('validates the exact completion boundary and immutable receipt', () => {
    const request = {
      schemaVersion: 1 as const,
      claimToken: 'review-claim-one',
      idempotencyKey: 'review-complete-one',
      verdict: 16,
      comment: 'Хорошая идея, поправьте обоснование.',
      confirmWithoutComment: false,
      branches: branches.map((branch, index) => ({
        queueId: branch.queueId,
        leaseVersion: 1,
        threadId: `thread-${index + 1}`,
        threadVersion: 2,
        evidence: [{ entryId: `entry-${index + 1}`, entryVersion: 2 }],
      })),
      annotations: [
        {
          attachmentId: 'attachment-one',
          schemaVersion: 1 as const,
          rotation: 90 as const,
          marks: [
            {
              markId: 'mark-pencil-one',
              kind: 'pencil' as const,
              data: {
                points: [
                  { x: 0.1, y: 0.2 },
                  { x: 0.3, y: 0.4 },
                ],
                width: 0.01,
                color: 'red' as const,
              },
            },
            {
              markId: 'mark-text-one',
              kind: 'text' as const,
              data: {
                x: 0.4,
                y: 0.5,
                text: 'Проверьте переход',
                size: 0.04,
                color: 'blue' as const,
              },
            },
            {
              markId: 'mark-eraser-one',
              kind: 'eraser' as const,
              data: {
                points: [
                  { x: 0.2, y: 0.2 },
                  { x: 0.21, y: 0.22 },
                ],
                width: 0.02,
              },
            },
            {
              markId: 'mark-rectangle-one',
              kind: 'rectangle' as const,
              data: {
                x: 0.1,
                y: 0.7,
                width: 0.25,
                height: 0.15,
                strokeWidth: 0.006,
                color: 'graphite' as const,
              },
            },
            {
              markId: 'mark-highlight-one',
              kind: 'highlight' as const,
              data: { x: 0.4, y: 0.75, width: 0.3, height: 0.08 },
            },
          ],
        },
      ],
    }
    expect(completeReviewRequestSchema.parse(request)).toEqual(request)
    expect(
      completeReviewRequestSchema.safeParse({
        ...request,
        verdict: 11,
        comment: null,
      }).success,
    ).toBe(false)
    expect(
      completeReviewResponseSchema.parse({
        schemaVersion: 1,
        review: {
          reviewId: 'review-one',
          targetThreadId: 'thread-2',
          targetProblemId: 'problem-two',
          targetThreadStatus: 'accepted',
          verdict: 16,
          commentEntryId: 'comment-one',
          evidenceEntryIds: ['entry-1', 'entry-2'],
          annotations: [
            {
              annotationId: 'annotation-one',
              attachmentId: 'attachment-one',
              schemaVersion: 1,
              rotation: 90,
              markCount: 5,
            },
          ],
          completedAt: '2026-10-04T12:10:00.000000Z',
          replayed: false,
        },
        requestId: 'request-review-complete',
      }).review.targetProblemId,
    ).toBe('problem-two')
    expect(
      completeReviewRequestSchema.safeParse({
        ...request,
        annotations: [
          {
            ...request.annotations[0],
            marks: [
              {
                markId: 'bad-rectangle',
                kind: 'rectangle',
                data: {
                  x: 0.9,
                  y: 0.9,
                  width: 0.2,
                  height: 0.2,
                  strokeWidth: 0.01,
                  color: 'red',
                },
              },
            ],
          },
        ],
      }).success,
    ).toBe(false)
  })

  it('rejects a lease whose evidence branches do not match the claim', () => {
    expect(
      reviewLeaseResponseSchema.safeParse({
        schemaVersion: 1,
        lease: {
          claimToken: 'review-claim-one',
          logicalCaseId: 'synonym-shared',
          student: { studentId: 'student-one', displayName: 'Анна Белова' },
          claimedAt: '2026-10-04T12:05:00.000000Z',
          expiresAt: '2026-10-04T12:35:00.000000Z',
          branches,
          evidenceBranches: evidenceBranches.slice(0, 1),
        },
        requestId: 'request-review-claim',
      }).success,
    ).toBe(false)
  })

  it('keeps list cache keys scoped by filters and cursor', () => {
    expect(reviewQueueQueryKeys.list(principal)).toEqual([
      'principal',
      'staff',
      'staff-reviewer',
      'review-queue',
      'all',
      'oldest',
      'first',
    ])
    expect(
      reviewQueueQueryKeys.list(principal, {
        problemGroup: 'synonym-shared',
        sort: 'newest',
        cursor: 'review-queue-one',
      }),
    ).toEqual([
      'principal',
      'staff',
      'staff-reviewer',
      'review-queue',
      'synonym-shared',
      'newest',
      'review-queue-one',
    ])
  })
})

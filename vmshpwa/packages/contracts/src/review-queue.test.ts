import { describe, expect, it } from 'vitest'

import {
  claimReviewItemRequestSchema,
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

describe('Phase-6 review queue contracts', () => {
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

  it('keeps list cache keys scoped by filters and cursor', () => {
    expect(reviewQueueQueryKeys.list()).toEqual(['staff', 'review-queue', 'all', 'oldest', 'first'])
    expect(
      reviewQueueQueryKeys.list({
        problemGroup: 'synonym-shared',
        sort: 'newest',
        cursor: 'review-queue-one',
      }),
    ).toEqual(['staff', 'review-queue', 'synonym-shared', 'newest', 'review-queue-one'])
  })
})

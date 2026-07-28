import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

/** Phase-6 review queue wire contract; see development-plan Phase 6. */
export const REVIEW_QUEUE_CONTRACT_VERSION = 1 as const
const contractVersionSchema = z.literal(REVIEW_QUEUE_CONTRACT_VERSION)

export const reviewQueueListQuerySchema = z
  .object({
    problemGroup: publicIdSchema.optional(),
    sort: z.enum(['oldest', 'newest']).default('oldest'),
    cursor: publicIdSchema.optional(),
  })
  .strict()
export type ReviewQueueListQuery = z.input<typeof reviewQueueListQuerySchema>

export const claimReviewItemRequestSchema = z
  .object({ schemaVersion: contractVersionSchema })
  .strict()
export type ClaimReviewItemRequest = z.infer<typeof claimReviewItemRequestSchema>

export const mutateReviewLeaseRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    claimToken: publicIdSchema,
  })
  .strict()
export type MutateReviewLeaseRequest = z.infer<typeof mutateReviewLeaseRequestSchema>

export const reviewQueueBranchSchema = z
  .object({
    queueId: publicIdSchema,
    problemId: publicIdSchema,
    problemTitle: z.string().trim().min(1),
    courseId: publicIdSchema.nullable(),
    groupId: publicIdSchema.nullable(),
    submittedAt: z.iso.datetime(),
    leaseVersion: z.number().int().nonnegative(),
  })
  .strict()
export type ReviewQueueBranch = z.infer<typeof reviewQueueBranchSchema>

const reviewStudentSchema = z
  .object({
    studentId: publicIdSchema.nullable(),
    displayName: z.string().trim().min(1),
  })
  .strict()

const reviewQueueLockSchema = z
  .object({
    kind: z.enum(['pwa', 'legacy']),
    teacher: z
      .object({
        teacherId: publicIdSchema.nullable(),
        displayName: z.string().trim().min(1),
      })
      .strict(),
    expiresAt: z.iso.datetime(),
    isOwnedByCurrentStaff: z.boolean(),
  })
  .strict()

export const reviewQueueItemSchema = z
  .object({
    queueId: publicIdSchema,
    logicalCaseId: publicIdSchema,
    student: reviewStudentSchema,
    submittedAt: z.iso.datetime(),
    branches: z.array(reviewQueueBranchSchema).min(1),
    lock: reviewQueueLockSchema.nullable(),
  })
  .strict()
  .superRefine((item, context) => {
    if (item.queueId !== item.branches[0]?.queueId) {
      context.addIssue({
        code: 'custom',
        message: 'Queue identity must point at the oldest logical-case branch',
        path: ['queueId'],
      })
    }
    for (let index = 1; index < item.branches.length; index += 1) {
      const previous = item.branches[index - 1]
      const current = item.branches[index]
      if (previous && current && current.submittedAt < previous.submittedAt) {
        context.addIssue({
          code: 'custom',
          message: 'Review branches must be chronological',
          path: ['branches', index, 'submittedAt'],
        })
      }
    }
  })
export type ReviewQueueItem = z.infer<typeof reviewQueueItemSchema>

export const reviewQueueListResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    items: z.array(reviewQueueItemSchema),
    nextCursor: publicIdSchema.nullable(),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type ReviewQueueListResponse = z.infer<typeof reviewQueueListResponseSchema>

export const reviewLeaseSchema = z
  .object({
    claimToken: publicIdSchema,
    logicalCaseId: publicIdSchema,
    student: reviewStudentSchema,
    claimedAt: z.iso.datetime(),
    expiresAt: z.iso.datetime(),
    branches: z.array(reviewQueueBranchSchema).min(1),
  })
  .strict()
  .refine((lease) => lease.expiresAt > lease.claimedAt, {
    message: 'Review lease must expire after it was claimed',
    path: ['expiresAt'],
  })
export type ReviewLease = z.infer<typeof reviewLeaseSchema>

export const reviewLeaseResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    lease: reviewLeaseSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type ReviewLeaseResponse = z.infer<typeof reviewLeaseResponseSchema>

export const releaseReviewLeaseResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    releasedItems: z.number().int().positive(),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type ReleaseReviewLeaseResponse = z.infer<typeof releaseReviewLeaseResponseSchema>

export const reviewQueueQueryKeys = {
  all: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'review-queue'] as const,
  list: (principal: PrincipalQueryScope, query: ReviewQueueListQuery = {}) => {
    const parsed = reviewQueueListQuerySchema.parse(query)
    return [
      ...reviewQueueQueryKeys.all(principal),
      parsed.problemGroup ?? 'all',
      parsed.sort,
      parsed.cursor ?? 'first',
    ] as const
  },
  lease: (principal: PrincipalQueryScope, queueId: string) =>
    [...principalQueryKey(principal), 'review-lease', publicIdSchema.parse(queueId)] as const,
} as const

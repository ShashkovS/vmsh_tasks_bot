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

export const reviewEvidenceAttachmentSchema = z
  .object({
    attachmentId: publicIdSchema,
    ordinal: z.number().int().nonnegative(),
  })
  .strict()
export type ReviewEvidenceAttachment = z.infer<typeof reviewEvidenceAttachmentSchema>

export const reviewEvidenceEntrySchema = z
  .object({
    entryId: publicIdSchema,
    entryVersion: z.number().int().positive(),
    entryKind: z.enum(['text', 'submission']),
    text: z.string().max(100_000).nullable(),
    submittedAt: z.iso.datetime(),
    attachments: z.array(reviewEvidenceAttachmentSchema).max(10),
  })
  .strict()
export type ReviewEvidenceEntry = z.infer<typeof reviewEvidenceEntrySchema>

export const reviewLeaseEvidenceBranchSchema = z
  .object({
    queueId: publicIdSchema,
    thread: z
      .object({
        threadId: publicIdSchema,
        threadVersion: z.number().int().positive(),
        entries: z.array(reviewEvidenceEntrySchema),
      })
      .strict()
      .nullable(),
  })
  .strict()
export type ReviewLeaseEvidenceBranch = z.infer<typeof reviewLeaseEvidenceBranchSchema>

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
    evidenceBranches: z.array(reviewLeaseEvidenceBranchSchema).min(1),
  })
  .strict()
  .refine((lease) => lease.expiresAt > lease.claimedAt, {
    message: 'Review lease must expire after it was claimed',
    path: ['expiresAt'],
  })
  .superRefine((lease, context) => {
    const queueIds = lease.branches.map((branch) => branch.queueId)
    const evidenceQueueIds = lease.evidenceBranches.map((branch) => branch.queueId)
    if (
      new Set(queueIds).size !== queueIds.length ||
      new Set(evidenceQueueIds).size !== evidenceQueueIds.length ||
      queueIds.length !== evidenceQueueIds.length ||
      queueIds.some((queueId) => !evidenceQueueIds.includes(queueId))
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Lease evidence must match the claimed queue branches',
        path: ['evidenceBranches'],
      })
    }
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

export const writtenReviewVerdictSchema = z.number().int().min(11).max(17)
export type WrittenReviewVerdict = z.infer<typeof writtenReviewVerdictSchema>

export const completeReviewEvidenceEntrySchema = z
  .object({
    entryId: publicIdSchema,
    entryVersion: z.number().int().positive(),
  })
  .strict()

export const completeReviewBranchSchema = z
  .object({
    queueId: publicIdSchema,
    leaseVersion: z.number().int().positive(),
    threadId: publicIdSchema,
    threadVersion: z.number().int().positive(),
    evidence: z.array(completeReviewEvidenceEntrySchema).min(1),
  })
  .strict()

export const completeReviewRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    claimToken: publicIdSchema,
    idempotencyKey: publicIdSchema,
    verdict: writtenReviewVerdictSchema,
    comment: z.string().max(100_000).nullable(),
    confirmWithoutComment: z.boolean(),
    branches: z.array(completeReviewBranchSchema).min(1),
  })
  .strict()
  .superRefine((request, context) => {
    if (request.verdict !== 17 && !request.comment?.trim() && !request.confirmWithoutComment) {
      context.addIssue({
        code: 'custom',
        message: 'A non-accepted verdict without a comment requires confirmation',
        path: ['confirmWithoutComment'],
      })
    }
    const queueIds = request.branches.map((branch) => branch.queueId)
    if (new Set(queueIds).size !== queueIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Completion branches must have unique queue IDs',
        path: ['branches'],
      })
    }
  })
export type CompleteReviewRequest = z.infer<typeof completeReviewRequestSchema>

export const completedReviewSchema = z
  .object({
    reviewId: publicIdSchema,
    targetThreadId: publicIdSchema,
    targetProblemId: publicIdSchema,
    targetThreadStatus: z.enum(['accepted', 'needs_work']),
    verdict: writtenReviewVerdictSchema,
    commentEntryId: publicIdSchema.nullable(),
    evidenceEntryIds: z.array(publicIdSchema).min(1),
    completedAt: z.iso.datetime(),
    replayed: z.boolean(),
  })
  .strict()
export type CompletedReview = z.infer<typeof completedReviewSchema>

export const completeReviewResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    review: completedReviewSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type CompleteReviewResponse = z.infer<typeof completeReviewResponseSchema>

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

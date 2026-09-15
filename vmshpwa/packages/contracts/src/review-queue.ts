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
    problemNumber: z.string().trim().min(1).max(64),
    problemTitle: z.string().trim().min(1),
    courseId: publicIdSchema.nullable(),
    courseName: z.string().trim().min(1).nullable(),
    groupId: publicIdSchema.nullable(),
    groupName: z.string().trim().min(1),
    groupShortCode: z.string().trim().min(1).max(16),
    groupColorKey: z.string().trim().min(1).max(64).nullable(),
    submittedAt: z.iso.datetime(),
    leaseVersion: z.number().int().nonnegative(),
  })
  .strip()
export type ReviewQueueBranch = z.infer<typeof reviewQueueBranchSchema>

export const reviewEvidenceAttachmentSchema = z
  .object({
    attachmentId: publicIdSchema,
    ordinal: z.number().int().nonnegative(),
  })
  .strip()
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
  .strip()
export type ReviewEvidenceEntry = z.infer<typeof reviewEvidenceEntrySchema>

export const reviewTimelineEntrySchema = z
  .object({
    entryId: publicIdSchema,
    authorKind: z.enum(['student', 'teacher', 'admin', 'ai', 'system']),
    entryKind: z.enum(['text', 'submission', 'teacher_comment', 'ai_comment', 'system_event']),
    text: z.string().max(100_000).nullable(),
    submittedAt: z.iso.datetime(),
    attachments: z.array(reviewEvidenceAttachmentSchema).max(10),
  })
  .strip()
export type ReviewTimelineEntry = z.infer<typeof reviewTimelineEntrySchema>

export const reviewLeaseEvidenceBranchSchema = z
  .object({
    queueId: publicIdSchema,
    thread: z
      .object({
        threadId: publicIdSchema,
        threadVersion: z.number().int().positive(),
        entries: z.array(reviewEvidenceEntrySchema),
        timelineEntries: z.array(reviewTimelineEntrySchema),
      })
      .strip()
      .nullable(),
  })
  .strip()
export type ReviewLeaseEvidenceBranch = z.infer<typeof reviewLeaseEvidenceBranchSchema>

const reviewStudentSchema = z
  .object({
    studentId: publicIdSchema.nullable(),
    displayName: z.string().trim().min(1),
  })
  .strip()

const reviewQueueLockSchema = z
  .object({
    kind: z.enum(['pwa', 'legacy']),
    teacher: z
      .object({
        teacherId: publicIdSchema.nullable(),
        displayName: z.string().trim().min(1),
      })
      .strip(),
    expiresAt: z.iso.datetime(),
    isOwnedByCurrentStaff: z.boolean(),
  })
  .strip()

export const reviewQueueItemSchema = z
  .object({
    queueId: publicIdSchema,
    logicalCaseId: publicIdSchema,
    student: reviewStudentSchema,
    submittedAt: z.iso.datetime(),
    branches: z.array(reviewQueueBranchSchema).min(1),
    lock: reviewQueueLockSchema.nullable(),
  })
  .strip()
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
  .strip()
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
    verdictMode: z
      .enum(['verdict_plus_minus', 'verdict_plus_minus_half', 'verdict_plus_steps'])
      .optional(),
  })
  .strip()
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
  .strip()
export type ReviewLeaseResponse = z.infer<typeof reviewLeaseResponseSchema>

export const releaseReviewLeaseResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    releasedItems: z.number().int().positive(),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ReleaseReviewLeaseResponse = z.infer<typeof releaseReviewLeaseResponseSchema>

export const writtenReviewVerdictSchema = z.number().int().min(11).max(17)
export type WrittenReviewVerdict = z.infer<typeof writtenReviewVerdictSchema>

export const writtenTeacherReactionIdSchema = z.union([
  z.literal(100),
  z.literal(101),
  z.literal(102),
  z.literal(103),
])
export type WrittenTeacherReactionId = z.infer<typeof writtenTeacherReactionIdSchema>

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

const annotationCoordinateSchema = z.number().min(0).max(1)
const annotationStrokeWidthSchema = z.number().min(0.001).max(0.1)
export const reviewAnnotationColorSchema = z.enum(['red', 'blue', 'graphite', 'amber'])
export type ReviewAnnotationColor = z.infer<typeof reviewAnnotationColorSchema>
const annotationPointSchema = z
  .object({ x: annotationCoordinateSchema, y: annotationCoordinateSchema })
  .strip()
const annotationBoxShape = {
  x: annotationCoordinateSchema,
  y: annotationCoordinateSchema,
  width: z.number().min(0.001).max(1),
  height: z.number().min(0.001).max(1),
}
const annotationBoxDataSchema = z
  .object(annotationBoxShape)
  .strip()
  .refine((box) => box.x + box.width <= 1 && box.y + box.height <= 1, {
    message: 'Annotation box must stay inside the evidence image',
  })

export const reviewAnnotationMarkSchema = z.discriminatedUnion('kind', [
  z
    .object({
      markId: publicIdSchema,
      coordinateSpace: z.literal('image').optional(),
      kind: z.literal('pencil'),
      data: z
        .object({
          points: z.array(annotationPointSchema).min(2).max(4096),
          width: annotationStrokeWidthSchema,
          color: reviewAnnotationColorSchema,
        })
        .strip(),
    })
    .strip(),
  z
    .object({
      markId: publicIdSchema,
      coordinateSpace: z.literal('image').optional(),
      kind: z.literal('eraser'),
      data: z
        .object({
          points: z.array(annotationPointSchema).min(2).max(4096),
          width: annotationStrokeWidthSchema,
        })
        .strip(),
    })
    .strip(),
  z
    .object({
      markId: publicIdSchema,
      coordinateSpace: z.literal('image').optional(),
      kind: z.literal('text'),
      data: z
        .object({
          x: annotationCoordinateSchema,
          y: annotationCoordinateSchema,
          text: z
            .string()
            .min(1)
            .max(500)
            .refine((value) => value.trim().length > 0, {
              message: 'Annotation text must not be blank',
            }),
          size: z.number().min(0.01).max(0.2),
          color: reviewAnnotationColorSchema,
        })
        .strip(),
    })
    .strip(),
  z
    .object({
      markId: publicIdSchema,
      coordinateSpace: z.literal('image').optional(),
      kind: z.literal('arrow'),
      data: z
        .object({
          start: annotationPointSchema,
          end: annotationPointSchema,
          width: annotationStrokeWidthSchema,
          color: reviewAnnotationColorSchema,
        })
        .strip()
        .refine((arrow) => arrow.start.x !== arrow.end.x || arrow.start.y !== arrow.end.y, {
          message: 'Annotation arrow must have a direction',
        }),
    })
    .strip(),
  z
    .object({
      markId: publicIdSchema,
      coordinateSpace: z.literal('image').optional(),
      kind: z.literal('rectangle'),
      data: z
        .object({
          ...annotationBoxShape,
          strokeWidth: annotationStrokeWidthSchema,
          color: reviewAnnotationColorSchema,
        })
        .strip()
        .refine((box) => box.x + box.width <= 1 && box.y + box.height <= 1, {
          message: 'Annotation rectangle must stay inside the evidence image',
        }),
    })
    .strip(),
  z
    .object({
      markId: publicIdSchema,
      coordinateSpace: z.literal('image').optional(),
      kind: z.literal('highlight'),
      data: annotationBoxDataSchema,
    })
    .strip(),
])
export type ReviewAnnotationMark = z.infer<typeof reviewAnnotationMarkSchema>

export const reviewAnnotationManifestSchema = z
  .object({
    attachmentId: publicIdSchema,
    schemaVersion: z.literal(1),
    rotation: z.union([z.literal(0), z.literal(90), z.literal(180), z.literal(270)]),
    marks: z.array(reviewAnnotationMarkSchema).min(1).max(250),
  })
  .strip()
  .superRefine((manifest, context) => {
    const markIds = manifest.marks.map((mark) => mark.markId)
    if (new Set(markIds).size !== markIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Annotation mark IDs must be unique',
        path: ['marks'],
      })
    }
    const pointCount = manifest.marks.reduce(
      (count, mark) =>
        count + (mark.kind === 'pencil' || mark.kind === 'eraser' ? mark.data.points.length : 0),
      0,
    )
    if (pointCount > 20_000) {
      context.addIssue({
        code: 'custom',
        message: 'Annotation manifest has too many points',
        path: ['marks'],
      })
    }
  })
export type ReviewAnnotationManifest = z.infer<typeof reviewAnnotationManifestSchema>

export const completeReviewRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    claimToken: publicIdSchema,
    idempotencyKey: publicIdSchema,
    verdict: writtenReviewVerdictSchema,
    comment: z.string().max(100_000).nullable(),
    confirmWithoutComment: z.boolean(),
    branches: z.array(completeReviewBranchSchema).min(1),
    annotations: z.array(reviewAnnotationManifestSchema).max(10),
    internalReactionId: writtenTeacherReactionIdSchema.nullable(),
  })
  .strict()
  .superRefine((request, context) => {
    if (
      request.verdict !== 16 &&
      request.verdict !== 17 &&
      !request.comment?.trim() &&
      !request.confirmWithoutComment
    ) {
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
    const attachmentIds = request.annotations.map((annotation) => annotation.attachmentId)
    if (new Set(attachmentIds).size !== attachmentIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Review annotations must target unique attachments',
        path: ['annotations'],
      })
    }
  })
export type CompleteReviewRequest = z.infer<typeof completeReviewRequestSchema>

export const reviewInternalReactionSchema = z
  .object({
    reviewId: publicIdSchema,
    reactionId: writtenTeacherReactionIdSchema.nullable(),
    version: z.number().int().positive(),
    editableUntil: z.iso.datetime(),
    updatedAt: z.iso.datetime(),
    deleted: z.boolean(),
  })
  .strip()
  .refine((state) => state.deleted === (state.reactionId === null), {
    message: 'Deleted internal-reaction state must not expose a reaction ID',
    path: ['deleted'],
  })
  .refine((state) => state.updatedAt <= state.editableUntil, {
    message: 'Internal reaction update must be inside its edit window',
    path: ['updatedAt'],
  })
export type ReviewInternalReaction = z.infer<typeof reviewInternalReactionSchema>

export const setReviewInternalReactionRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    reactionId: writtenTeacherReactionIdSchema,
    expectedVersion: z.number().int().nonnegative(),
  })
  .strict()
export type SetReviewInternalReactionRequest = z.infer<
  typeof setReviewInternalReactionRequestSchema
>

export const deleteReviewInternalReactionRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    expectedVersion: z.number().int().positive(),
  })
  .strict()
export type DeleteReviewInternalReactionRequest = z.infer<
  typeof deleteReviewInternalReactionRequestSchema
>

export const reviewInternalReactionResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    internalReaction: reviewInternalReactionSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ReviewInternalReactionResponse = z.infer<typeof reviewInternalReactionResponseSchema>

export const completedReviewSchema = z
  .object({
    reviewId: publicIdSchema,
    targetThreadId: publicIdSchema,
    targetProblemId: publicIdSchema,
    targetThreadStatus: z.enum(['accepted', 'needs_work']),
    verdict: writtenReviewVerdictSchema,
    commentEntryId: publicIdSchema.nullable(),
    evidenceEntryIds: z.array(publicIdSchema).min(1),
    annotations: z.array(
      z
        .object({
          annotationId: publicIdSchema,
          attachmentId: publicIdSchema,
          schemaVersion: z.literal(1),
          rotation: z.union([z.literal(0), z.literal(90), z.literal(180), z.literal(270)]),
          markCount: z.number().int().min(1).max(250),
        })
        .strip(),
    ),
    internalReaction: reviewInternalReactionSchema.nullable(),
    completedAt: z.iso.datetime(),
    replayed: z.boolean(),
  })
  .strip()
export type CompletedReview = z.infer<typeof completedReviewSchema>

export const completeReviewResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    review: completedReviewSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
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
  review: (principal: PrincipalQueryScope, reviewId: string) =>
    [...principalQueryKey(principal), 'review', publicIdSchema.parse(reviewId)] as const,
} as const

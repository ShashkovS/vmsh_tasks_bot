import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { reviewAnnotationManifestSchema, writtenReviewVerdictSchema } from './review-queue'

/** Phase-5 written-thread wire boundary; see development-plan Phase 5. */
export const WRITTEN_SUBMISSION_CONTRACT_VERSION = 1 as const
const contractVersionSchema = z.literal(WRITTEN_SUBMISSION_CONTRACT_VERSION)
const utcClientTimeSchema = z.iso
  .datetime()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/)

export const writtenProblemRevisionSchema = z
  .object({
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
  })
  .strict()
export type WrittenProblemRevision = z.infer<typeof writtenProblemRevisionSchema>

const writtenAttachmentShape = {
  attachmentId: publicIdSchema,
  ordinal: z.number().int().nonnegative(),
  uploadStatus: z.enum(['pending', 'stored', 'failed', 'locked']),
  mediaId: publicIdSchema,
  publicUrl: z.url().nullable(),
  mediaType: z.literal('image/webp'),
  width: z.number().int().min(1).max(1920),
  height: z.number().int().min(1).max(1920),
}

export const writtenAttachmentSchema = z
  .object({
    ...writtenAttachmentShape,
    mediaPath: z
      .string()
      .regex(
        /^\/student\/api\/v1\/thread-entries\/[a-z0-9][a-z0-9._:-]*\/attachments\/[a-z0-9][a-z0-9._:-]*\/media$/,
      ),
  })
  .strict()
export type WrittenAttachment = z.infer<typeof writtenAttachmentSchema>

export const staffWrittenAttachmentSchema = z
  .object({
    ...writtenAttachmentShape,
    mediaPath: z
      .string()
      .regex(
        /^\/staff\/api\/v1\/thread-entries\/[a-z0-9][a-z0-9._:-]*\/attachments\/[a-z0-9][a-z0-9._:-]*\/media$/,
      ),
  })
  .strict()
export type StaffWrittenAttachment = z.infer<typeof staffWrittenAttachmentSchema>

export const writtenMaterialProjectionSchema = z
  .object({
    kind: z.literal('staff_reassignment'),
    reassignmentIds: z.array(publicIdSchema).min(1).max(100),
    sourceThreadId: publicIdSchema,
    sourceProblemId: publicIdSchema,
    targetThreadId: publicIdSchema,
    targetProblemId: publicIdSchema,
    movedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((projection, context) => {
    if (projection.sourceThreadId === projection.targetThreadId) {
      context.addIssue({
        code: 'custom',
        message: 'A reassignment must change the projected thread',
        path: ['targetThreadId'],
      })
    }
    if (new Set(projection.reassignmentIds).size !== projection.reassignmentIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Reassignment IDs must be unique',
        path: ['reassignmentIds'],
      })
    }
  })
export type WrittenMaterialProjection = z.infer<typeof writtenMaterialProjectionSchema>

export const writtenEntrySchema = z
  .object({
    entryId: publicIdSchema,
    authorKind: z.enum(['student', 'teacher', 'admin', 'ai', 'system']),
    entryKind: z.enum(['text', 'submission', 'teacher_comment', 'ai_comment', 'system_event']),
    state: z.enum(['draft', 'uploading', 'submitted', 'deleted', 'locked']),
    text: z.string().max(100_000).nullable(),
    problemRevision: writtenProblemRevisionSchema.nullable(),
    version: z.number().int().positive(),
    clientCreatedAt: z.iso.datetime().nullable(),
    serverReceivedAt: z.iso.datetime(),
    attachments: z.array(writtenAttachmentSchema).max(10),
    projection: writtenMaterialProjectionSchema.optional(),
  })
  .strict()
  .superRefine((entry, context) => {
    if (entry.authorKind === 'student' && entry.problemRevision === null) {
      context.addIssue({
        code: 'custom',
        message: 'Student material must keep exact problem-revision provenance',
        path: ['problemRevision'],
      })
    }
    const ordinals = entry.attachments.map((attachment) => attachment.ordinal)
    if (new Set(ordinals).size !== ordinals.length) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment ordinals must be unique',
        path: ['attachments'],
      })
    }
    if (
      ['submitted', 'locked'].includes(entry.state) &&
      !entry.text?.trim() &&
      entry.attachments.length === 0
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Submitted material must contain text or an attachment',
        path: ['state'],
      })
    }
  })
export type WrittenEntry = z.infer<typeof writtenEntrySchema>

/** Student-visible immutable review projection. Internal Teacher reactions are excluded. */
export const writtenReviewProjectionSchema = z
  .object({
    reviewId: publicIdSchema,
    targetProblemId: publicIdSchema,
    verdict: writtenReviewVerdictSchema,
    commentEntryId: publicIdSchema.nullable(),
    comment: z.string().max(100_000).nullable(),
    reviewerName: z.string().trim().min(1).max(500),
    source: z.enum(['staff', 'telegram', 'ai']),
    evidenceEntryIds: z.array(publicIdSchema).min(1),
    annotations: z.array(reviewAnnotationManifestSchema).max(10),
    completedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((review, context) => {
    if (new Set(review.evidenceEntryIds).size !== review.evidenceEntryIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Review evidence entry IDs must be unique',
        path: ['evidenceEntryIds'],
      })
    }
  })
export type WrittenReviewProjection = z.infer<typeof writtenReviewProjectionSchema>

export const writtenThreadSchema = z
  .object({
    threadId: publicIdSchema,
    problemId: publicIdSchema,
    status: z.enum(['open', 'awaiting_review', 'needs_work', 'accepted', 'closed']),
    conditionRevisionId: publicIdSchema,
    version: z.number().int().positive(),
    latestEntryAt: z.iso.datetime(),
    entries: z.array(writtenEntrySchema),
    reviews: z.array(writtenReviewProjectionSchema),
  })
  .strict()
  .superRefine((thread, context) => {
    let previous: string | null = null
    const seen = new Set<string>()
    thread.entries.forEach((entry, index) => {
      if (seen.has(entry.entryId)) {
        context.addIssue({
          code: 'custom',
          message: 'Thread entry IDs must be unique',
          path: ['entries', index, 'entryId'],
        })
      }
      if (previous !== null && entry.serverReceivedAt < previous) {
        context.addIssue({
          code: 'custom',
          message: 'Thread entries must use chronological order',
          path: ['entries', index, 'serverReceivedAt'],
        })
      }
      seen.add(entry.entryId)
      previous = entry.serverReceivedAt
    })
    const entryIds = new Set(thread.entries.map((entry) => entry.entryId))
    const attachmentIds = new Set(
      thread.entries.flatMap((entry) =>
        entry.attachments.map((attachment) => attachment.attachmentId),
      ),
    )
    const reviewIds = new Set<string>()
    thread.reviews.forEach((review, reviewIndex) => {
      if (reviewIds.has(review.reviewId)) {
        context.addIssue({
          code: 'custom',
          message: 'Review IDs must be unique',
          path: ['reviews', reviewIndex, 'reviewId'],
        })
      }
      for (const [evidenceIndex, entryId] of review.evidenceEntryIds.entries()) {
        if (!entryIds.has(entryId)) {
          context.addIssue({
            code: 'custom',
            message: 'Review evidence must belong to this concrete thread',
            path: ['reviews', reviewIndex, 'evidenceEntryIds', evidenceIndex],
          })
        }
      }
      for (const [annotationIndex, annotation] of review.annotations.entries()) {
        if (!attachmentIds.has(annotation.attachmentId)) {
          context.addIssue({
            code: 'custom',
            message: 'Review annotation must target this concrete thread evidence',
            path: ['reviews', reviewIndex, 'annotations', annotationIndex, 'attachmentId'],
          })
        }
      }
      reviewIds.add(review.reviewId)
    })
  })
export type WrittenThread = z.infer<typeof writtenThreadSchema>

export const createWrittenEntryRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    problemRevision: writtenProblemRevisionSchema,
    text: z.string().max(100_000).nullable(),
    clientCreatedAt: utcClientTimeSchema,
  })
  .strict()
export type CreateWrittenEntryRequest = z.infer<typeof createWrittenEntryRequestSchema>

const writtenEntryMutationShape = {
  schemaVersion: contractVersionSchema,
  threadId: publicIdSchema,
  problemId: publicIdSchema,
  threadStatus: z.enum(['open', 'awaiting_review', 'needs_work', 'accepted', 'closed']),
  threadVersion: z.number().int().positive(),
  entry: writtenEntrySchema,
  requestId: z.string().trim().min(1).max(200),
}

export const createWrittenEntryResponseSchema = z
  .object(writtenEntryMutationShape)
  .strict()
  .superRefine((response, context) => {
    if (
      response.entry.authorKind !== 'student' ||
      response.entry.entryKind !== 'submission' ||
      response.entry.state !== 'draft'
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Create response must contain the new Student draft',
        path: ['entry'],
      })
    }
  })
export type CreateWrittenEntryResponse = z.infer<typeof createWrittenEntryResponseSchema>

/** Typed text fields used to build the multipart attachment request. */
export const writtenAttachmentUploadMetadataSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    expectedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
    ordinal: z.number().int().min(0).max(9),
  })
  .strict()
export type WrittenAttachmentUploadMetadata = z.infer<typeof writtenAttachmentUploadMetadataSchema>

export const createWrittenAttachmentResponseSchema = z
  .object(writtenEntryMutationShape)
  .strict()
  .superRefine((response, context) => {
    if (
      response.entry.state !== 'draft' ||
      response.entry.attachments.length === 0 ||
      response.entry.attachments.some((attachment) => attachment.uploadStatus !== 'stored')
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment response must expose a stored image on the Student draft',
        path: ['entry', 'attachments'],
      })
    }
  })
export type CreateWrittenAttachmentResponse = z.infer<typeof createWrittenAttachmentResponseSchema>

export const reorderWrittenAttachmentsRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    expectedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
    attachmentIds: z.array(publicIdSchema).max(10),
  })
  .strict()
  .superRefine((request, context) => {
    if (new Set(request.attachmentIds).size !== request.attachmentIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment IDs must be unique',
        path: ['attachmentIds'],
      })
    }
  })
export type ReorderWrittenAttachmentsRequest = z.infer<
  typeof reorderWrittenAttachmentsRequestSchema
>

export const deleteWrittenAttachmentRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    expectedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
  })
  .strict()
export type DeleteWrittenAttachmentRequest = z.infer<typeof deleteWrittenAttachmentRequestSchema>

export const mutateWrittenAttachmentsResponseSchema = z
  .object({
    ...writtenEntryMutationShape,
    changed: z.boolean(),
  })
  .strict()
  .superRefine((response, context) => {
    if (
      response.entry.attachments.some(
        (attachment) => !['stored', 'locked'].includes(attachment.uploadStatus),
      )
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment mutations expose only durable evidence',
        path: ['entry', 'attachments'],
      })
    }
  })
export type MutateWrittenAttachmentsResponse = z.infer<
  typeof mutateWrittenAttachmentsResponseSchema
>

export const submitWrittenEntryRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    expectedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
    attachmentIds: z.array(publicIdSchema).max(10),
  })
  .strict()
  .superRefine((request, context) => {
    if (new Set(request.attachmentIds).size !== request.attachmentIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment IDs must be unique',
        path: ['attachmentIds'],
      })
    }
  })
export type SubmitWrittenEntryRequest = z.infer<typeof submitWrittenEntryRequestSchema>

export const submitWrittenEntryResponseSchema = z
  .object({
    ...writtenEntryMutationShape,
    clockSuspicious: z.boolean(),
  })
  .strict()
  .superRefine((response, context) => {
    if (response.threadStatus !== 'awaiting_review' || response.entry.state !== 'submitted') {
      context.addIssue({
        code: 'custom',
        message: 'Submit response must expose material awaiting review',
        path: ['threadStatus'],
      })
    }
  })
export type SubmitWrittenEntryResponse = z.infer<typeof submitWrittenEntryResponseSchema>

export const replaceWrittenEntryRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    replacedEntryId: publicIdSchema,
    expectedEntryVersion: z.number().int().positive(),
    expectedReplacedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
    attachmentIds: z.array(publicIdSchema).max(10),
  })
  .strict()
  .superRefine((request, context) => {
    if (new Set(request.attachmentIds).size !== request.attachmentIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment IDs must be unique',
        path: ['attachmentIds'],
      })
    }
  })
export type ReplaceWrittenEntryRequest = z.infer<typeof replaceWrittenEntryRequestSchema>

export const replaceWrittenEntryResponseSchema = z
  .object({
    ...writtenEntryMutationShape,
    replacedEntryId: publicIdSchema,
    replacementEventId: publicIdSchema,
    clockSuspicious: z.boolean(),
  })
  .strict()
  .superRefine((response, context) => {
    if (
      response.threadStatus !== 'awaiting_review' ||
      response.entry.state !== 'submitted' ||
      response.entry.entryId === response.replacedEntryId
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Replacement must expose new evidence awaiting review',
        path: ['entry'],
      })
    }
  })
export type ReplaceWrittenEntryResponse = z.infer<typeof replaceWrittenEntryResponseSchema>

export const writtenMaterialItemRefSchema = z
  .object({
    entryId: publicIdSchema,
    itemKind: z.enum(['entry_text', 'attachment']),
    attachmentId: publicIdSchema.nullable(),
  })
  .strict()
  .superRefine((item, context) => {
    const expectedAttachment = item.itemKind === 'attachment'
    if (expectedAttachment !== (item.attachmentId !== null)) {
      context.addIssue({
        code: 'custom',
        message: 'Only attachment items name an attachment',
        path: ['attachmentId'],
      })
    }
  })
export type WrittenMaterialItemRef = z.infer<typeof writtenMaterialItemRefSchema>

const writtenMaterialItemListSchema = z
  .array(writtenMaterialItemRefSchema)
  .min(1)
  .max(100)
  .superRefine((items, context) => {
    const keys = items.map(
      (item) => `${item.entryId}\u0000${item.itemKind}\u0000${item.attachmentId ?? ''}`,
    )
    if (new Set(keys).size !== keys.length) {
      context.addIssue({
        code: 'custom',
        message: 'A material item cannot be selected twice',
      })
    }
  })

export const previewWrittenMaterialReassignmentRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    sourceThreadId: publicIdSchema,
    targetProblemId: publicIdSchema,
    items: writtenMaterialItemListSchema,
  })
  .strict()
export type PreviewWrittenMaterialReassignmentRequest = z.infer<
  typeof previewWrittenMaterialReassignmentRequestSchema
>

export const writtenMaterialScopeSchema = z
  .object({
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    groupLessonId: publicIdSchema,
  })
  .strict()

const writtenMaterialPreviewItemSchema = writtenMaterialItemRefSchema
  .safeExtend({
    entryState: z.enum(['submitted', 'locked']),
    text: z.string().max(100_000).nullable(),
    attachment: staffWrittenAttachmentSchema.nullable(),
    locked: z.boolean(),
  })
  .superRefine((item, context) => {
    if (
      (item.itemKind === 'entry_text' && (item.text === null || item.attachment !== null)) ||
      (item.itemKind === 'attachment' && (item.text !== null || item.attachment === null))
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Preview content must match the selected item kind',
      })
    }
  })

const writtenMaterialSourcePreviewSchema = z
  .object({
    threadId: publicIdSchema,
    problemId: publicIdSchema,
    threadStatus: z.enum(['open', 'awaiting_review', 'needs_work', 'accepted', 'closed']),
    threadVersion: z.number().int().positive(),
    scope: writtenMaterialScopeSchema,
  })
  .strict()

const writtenMaterialTargetPreviewSchema = z
  .object({
    threadId: publicIdSchema.nullable(),
    problemId: publicIdSchema,
    threadVersion: z.number().int().positive().nullable(),
    scope: writtenMaterialScopeSchema,
  })
  .strict()
  .superRefine((target, context) => {
    if ((target.threadId === null) !== (target.threadVersion === null)) {
      context.addIssue({
        code: 'custom',
        message: 'Target thread identity and version must appear together',
      })
    }
  })

export const previewWrittenMaterialReassignmentResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    studentId: publicIdSchema,
    source: writtenMaterialSourcePreviewSchema,
    target: writtenMaterialTargetPreviewSchema,
    items: z.array(writtenMaterialPreviewItemSchema).min(1).max(100),
    impact: z
      .object({
        postReview: z.boolean(),
        sourceEvidenceUnchanged: z.literal(true),
        sourceVerdictUnchanged: z.literal(true),
        targetRequiresReview: z.literal(true),
        studentLabel: z.literal('Перенесено преподавателем'),
      })
      .strict(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
export type PreviewWrittenMaterialReassignmentResponse = z.infer<
  typeof previewWrittenMaterialReassignmentResponseSchema
>

export const reassignWrittenMaterialRequestSchema = z
  .object({
    ...previewWrittenMaterialReassignmentRequestSchema.shape,
    idempotencyKey: z.uuid(),
    expectedSourceThreadVersion: z.number().int().positive(),
    expectedTargetThreadVersion: z.number().int().positive().nullable(),
    reason: z.string().trim().min(1).max(2_000).nullable(),
  })
  .strict()
export type ReassignWrittenMaterialRequest = z.infer<typeof reassignWrittenMaterialRequestSchema>

const writtenMaterialMutationThreadSchema = z
  .object({
    threadId: publicIdSchema,
    problemId: publicIdSchema,
    threadStatus: z.enum(['awaiting_review', 'closed', 'needs_work', 'accepted']),
    threadVersion: z.number().int().positive(),
  })
  .strict()

export const reassignWrittenMaterialResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    reassignmentId: publicIdSchema,
    source: writtenMaterialMutationThreadSchema,
    target: writtenMaterialMutationThreadSchema.extend({
      threadStatus: z.literal('awaiting_review'),
    }),
    items: writtenMaterialItemListSchema,
    movedAt: z.iso.datetime(),
    studentLabel: z.literal('Перенесено преподавателем'),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((response, context) => {
    if (
      response.source.threadId === response.target.threadId ||
      response.source.problemId === response.target.problemId
    ) {
      context.addIssue({
        code: 'custom',
        message: 'A reassignment must target another concrete task',
        path: ['target'],
      })
    }
  })
export type ReassignWrittenMaterialResponse = z.infer<typeof reassignWrittenMaterialResponseSchema>

export const writtenSubmissionCompletionResponseSchema = z.union([
  submitWrittenEntryResponseSchema,
  replaceWrittenEntryResponseSchema,
])
export type WrittenSubmissionCompletionResponse = z.infer<
  typeof writtenSubmissionCompletionResponseSchema
>

export const writtenThreadResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    problemId: publicIdSchema,
    thread: writtenThreadSchema.nullable(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((response, context) => {
    if (response.thread !== null && response.thread.problemId !== response.problemId) {
      context.addIssue({
        code: 'custom',
        message: 'Thread must belong to the requested problem',
        path: ['thread', 'problemId'],
      })
    }
  })
export type WrittenThreadResponse = z.infer<typeof writtenThreadResponseSchema>

export const writtenSubmissionQueryKeys = {
  all: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'written-submissions'] as const,
  thread: (principal: PrincipalQueryScope, problemId: string) =>
    [
      ...writtenSubmissionQueryKeys.all(principal),
      'thread',
      publicIdSchema.parse(problemId),
    ] as const,
} as const

export const writtenSubmissionFixtureSchema = z
  .object({
    fixtureVersion: contractVersionSchema,
    createRequest: createWrittenEntryRequestSchema,
    createResponse: createWrittenEntryResponseSchema,
    attachmentMetadata: writtenAttachmentUploadMetadataSchema,
    attachmentResponse: createWrittenAttachmentResponseSchema,
    reorderRequest: reorderWrittenAttachmentsRequestSchema,
    reorderResponse: mutateWrittenAttachmentsResponseSchema,
    deleteRequest: deleteWrittenAttachmentRequestSchema,
    deleteResponse: mutateWrittenAttachmentsResponseSchema,
    submitRequest: submitWrittenEntryRequestSchema,
    submitResponse: submitWrittenEntryResponseSchema,
    replaceRequest: replaceWrittenEntryRequestSchema,
    replaceResponse: replaceWrittenEntryResponseSchema,
    threadResponse: writtenThreadResponseSchema,
  })
  .strict()

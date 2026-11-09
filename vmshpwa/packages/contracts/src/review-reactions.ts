import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import {
  reviewEvidenceEntrySchema,
  reviewAnnotationManifestSchema,
  writtenReviewVerdictSchema,
  writtenTeacherReactionIdSchema,
} from './review-queue'

const contractVersionSchema = z.literal(1)
export const writtenStudentReactionIdSchema = z.union([z.literal(0), z.literal(1), z.literal(2)])
export const reviewReactionIdSchema = z.union([
  writtenStudentReactionIdSchema,
  writtenTeacherReactionIdSchema,
])
export type ReviewReactionId = z.infer<typeof reviewReactionIdSchema>

export const reviewReactionInboxQuerySchema = z
  .object({
    kind: z.enum(['all', 'student', 'teacher']).default('all'),
    reactionId: reviewReactionIdSchema.optional(),
    cursor: publicIdSchema.optional(),
  })
  .strict()
  .superRefine((query, context) => {
    if (
      query.reactionId !== undefined &&
      ((query.kind === 'student' && query.reactionId >= 100) ||
        (query.kind === 'teacher' && query.reactionId < 100))
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Reaction ID must belong to the selected actor kind',
        path: ['reactionId'],
      })
    }
  })
export type ReviewReactionInboxQuery = z.input<typeof reviewReactionInboxQuerySchema>

const reactionPersonSchema = z
  .object({
    displayName: z.string().trim().min(1),
  })
  .strip()

const reactionStudentSchema = reactionPersonSchema.safeExtend({
  studentId: publicIdSchema.nullable(),
})

const reactionStaffSchema = reactionPersonSchema.safeExtend({
  staffId: publicIdSchema.nullable(),
})

const reactionProblemSchema = z
  .object({
    problemId: publicIdSchema,
    problemNumber: z.string().trim().min(1).max(64),
    problemTitle: z.string().trim().min(1),
    courseId: publicIdSchema.nullable(),
    courseName: z.string().trim().min(1).nullable(),
    groupId: publicIdSchema.nullable(),
    groupName: z.string().trim().min(1),
    groupShortCode: z.string().trim().min(1).max(16),
    groupColorKey: z.string().trim().min(1).max(64).nullable(),
  })
  .strip()

export const reviewReactionInboxItemSchema = z
  .object({
    itemId: publicIdSchema,
    reviewId: publicIdSchema,
    kind: z.enum(['student', 'teacher']),
    reactionId: reviewReactionIdSchema,
    reactionLabel: z.string().trim().min(1).max(500),
    reactionVersion: z.number().int().positive(),
    updatedAt: z.iso.datetime(),
    editableUntil: z.iso.datetime(),
    student: reactionStudentSchema,
    reviewer: reactionStaffSchema,
    problem: reactionProblemSchema,
    verdict: writtenReviewVerdictSchema,
    comment: z.string().max(100_000).nullable(),
    completedAt: z.iso.datetime(),
    isLatestReview: z.boolean(),
    evidenceEntries: z.array(reviewEvidenceEntrySchema).min(1),
  })
  .strip()
  .superRefine((item, context) => {
    if (
      (item.kind === 'student' && item.reactionId >= 100) ||
      (item.kind === 'teacher' && item.reactionId < 100)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Reaction ID does not match its actor kind',
        path: ['reactionId'],
      })
    }
    if (item.updatedAt > item.editableUntil) {
      context.addIssue({
        code: 'custom',
        message: 'Reaction update must be inside its edit window',
        path: ['updatedAt'],
      })
    }
  })
export type ReviewReactionInboxItem = z.infer<typeof reviewReactionInboxItemSchema>

export const reviewReactionInboxResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    items: z.array(reviewReactionInboxItemSchema),
    nextCursor: publicIdSchema.nullable(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strip()
export type ReviewReactionInboxResponse = z.infer<typeof reviewReactionInboxResponseSchema>

export const correctWrittenReviewRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: publicIdSchema,
    verdict: writtenReviewVerdictSchema,
    comment: z.string().max(100_000).nullable(),
    confirmWithoutComment: z.boolean(),
    annotations: z.array(reviewAnnotationManifestSchema).max(10).optional(),
    expectedLatestReviewId: publicIdSchema.optional(),
    expectedThreadVersion: z.number().int().positive().optional(),
    confirmReplaceNewer: z.boolean().optional(),
  })
  .strict()
  .superRefine((request, context) => {
    const extended =
      request.annotations !== undefined ||
      request.expectedLatestReviewId !== undefined ||
      request.expectedThreadVersion !== undefined ||
      request.confirmReplaceNewer !== undefined
    if (
      extended &&
      (request.expectedLatestReviewId === undefined ||
        request.expectedThreadVersion === undefined ||
        request.confirmReplaceNewer === undefined)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Correction requires both current versions and explicit replacement confirmation',
      })
    }
    if (
      request.annotations &&
      new Set(request.annotations.map((item) => item.attachmentId)).size !==
        request.annotations.length
    ) {
      context.addIssue({ code: 'custom', message: 'Duplicate annotation attachment' })
    }
  })
export type CorrectWrittenReviewRequest = z.infer<typeof correctWrittenReviewRequestSchema>

export const correctWrittenReviewResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    correction: z
      .object({
        reviewId: publicIdSchema,
        correctsReviewId: publicIdSchema,
        threadId: publicIdSchema,
        problemId: publicIdSchema,
        verdict: writtenReviewVerdictSchema,
        threadStatus: z.enum(['accepted', 'needs_work']),
        completedAt: z.iso.datetime(),
        replayed: z.boolean(),
      })
      .strip(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strip()
export type CorrectWrittenReviewResponse = z.infer<typeof correctWrittenReviewResponseSchema>

export const reviewReactionInboxQueryKeys = {
  all: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'review-reactions'] as const,
  list: (principal: PrincipalQueryScope, query: ReviewReactionInboxQuery = {}) => {
    const parsed = reviewReactionInboxQuerySchema.parse(query)
    return [
      ...reviewReactionInboxQueryKeys.all(principal),
      parsed.kind,
      parsed.reactionId ?? 'all',
      parsed.cursor ?? 'first',
    ] as const
  },
} as const

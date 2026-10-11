import { z } from 'zod'
import { publicIdSchema } from './auth'
import { webContentDocumentSchema } from './content'
import {
  reviewAnnotationManifestSchema,
  reviewLeaseSchema,
  writtenReviewVerdictSchema,
  writtenTeacherReactionIdSchema,
} from './review-queue'
import { studentResultEventSchema } from './student-results'
import { reviewTransferRequestSchema } from './review-series'

/** Lease-free snapshot contracts; docs/review-sheet.md and StaffReviewSheetPage. */
export const reviewSheetSearchSchema = z.object({
  lesson: publicIdSchema.optional().catch(undefined),
  problem: publicIdSchema.optional().catch(undefined),
  mode: z.enum(['pending', 'all']).default('pending').catch('pending'),
})
export type ReviewSheetSearch = z.infer<typeof reviewSheetSearchSchema>
const envelope = { schemaVersion: z.literal(1), requestId: z.string() }
const snapshotSchema = z.string().regex(/^[0-9a-f]{64}$/)
export const reviewSheetOptionsSchema = z
  .object({
    ...envelope,
    lessons: z.array(z.object({ lessonId: publicIdSchema, label: z.string() }).strip()),
  })
  .strip()
export const reviewSheetCollectionSchema = z
  .object({
    ...envelope,
    lessonId: publicIdSchema,
    total: z.number().int().nonnegative(),
    limit: z.literal(300),
    canOpenLesson: z.boolean(),
    tasks: z.array(
      z
        .object({
          problemId: publicIdSchema,
          label: z.string(),
          count: z.number().int().nonnegative(),
          parts: z.array(
            z
              .object({
                problemId: publicIdSchema,
                label: z.string(),
                condition: webContentDocumentSchema.nullable(),
                statement: z.string(),
              })
              .strip(),
          ),
          cases: z.array(
            z
              .object({
                caseId: publicIdSchema,
                problemId: publicIdSchema,
                studentName: z.string(),
                submittedAt: z.iso.datetime(),
                pending: z.boolean(),
              })
              .strip(),
          ),
        })
        .strip(),
    ),
  })
  .strip()
export const reviewSheetWorkspaceSchema = z
  .object({
    logicalCaseId: publicIdSchema,
    student: reviewLeaseSchema.shape.student,
    branches: reviewLeaseSchema.shape.branches,
    evidenceBranches: reviewLeaseSchema.shape.evidenceBranches,
    verdictMode: reviewLeaseSchema.shape.verdictMode,
  })
  .strip()
export type ReviewWorkspaceEvidence = z.infer<typeof reviewSheetWorkspaceSchema>
export const reviewSheetDetailSchema = z
  .object({
    ...envelope,
    caseId: publicIdSchema,
    snapshot: snapshotSchema,
    pending: z.boolean(),
    canReview: z.boolean(),
    workspace: reviewSheetWorkspaceSchema,
    annotations: z.array(reviewAnnotationManifestSchema),
    currentReview: z
      .object({
        reviewId: publicIdSchema,
        verdict: writtenReviewVerdictSchema,
        comment: z.string(),
        teacherName: z.string(),
        completedAt: z.iso.datetime(),
      })
      .strip()
      .nullable(),
  })
  .strip()
export const reviewSheetCompleteRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    snapshot: snapshotSchema,
    idempotencyKey: publicIdSchema,
    verdict: writtenReviewVerdictSchema,
    comment: z.string().max(100_000).nullable(),
    confirmWithoutComment: z.boolean(),
    annotations: z.array(reviewAnnotationManifestSchema).max(10),
    internalReactionId: writtenTeacherReactionIdSchema.nullable(),
  })
  .strict()
export const reviewSheetConversationSchema = z
  .object({
    ...envelope,
    events: z.array(
      studentResultEventSchema.extend({
        problemNumber: z.string(),
        internal: z.literal(false),
        attachments: z.array(
          studentResultEventSchema.shape.attachments.element.extend({
            url: z
              .string()
              .regex(
                /^\/staff\/api\/v1\/review\/sheet\/st-[0-9]+\/(?:attachments|legacy-attachments)\/[a-z0-9._:-]+$/,
              ),
          }),
        ),
      }),
    ),
    nextCursor: z.string().nullable(),
    total: z.number().int().nonnegative(),
  })
  .strip()
export type ReviewSheetOptions = z.infer<typeof reviewSheetOptionsSchema>
export type ReviewSheetCollection = z.infer<typeof reviewSheetCollectionSchema>
export type ReviewSheetDetail = z.infer<typeof reviewSheetDetailSchema>
export type ReviewSheetCompleteRequest = z.infer<typeof reviewSheetCompleteRequestSchema>
export type ReviewSheetConversation = z.infer<typeof reviewSheetConversationSchema>
export const reviewSheetTransferPreviewRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    entryId: publicIdSchema,
    snapshot: snapshotSchema,
  })
  .strict()
export const reviewSheetTransferRequestSchema = reviewTransferRequestSchema
  .omit({ claimToken: true })
  .extend({ snapshot: snapshotSchema })
  .strict()
export type ReviewSheetTransferRequest = z.infer<typeof reviewSheetTransferRequestSchema>

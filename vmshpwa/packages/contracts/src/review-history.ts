import { z } from 'zod'
import { publicIdSchema } from './auth'
import { webContentDocumentSchema } from './content'
import { reviewAnnotationManifestSchema, writtenReviewVerdictSchema } from './review-queue'

// Authoritative flow: docs/review-history.md.
const named = z.object({ id: publicIdSchema, name: z.string() }).strict()
export const reviewHistoryItemSchema = z
  .object({
    reviewId: publicIdSchema,
    verdict: writtenReviewVerdictSchema,
    completedAt: z.iso.datetime(),
    studentId: publicIdSchema,
    studentName: z.string(),
    isTestStudent: z.boolean(),
    teacherId: publicIdSchema,
    teacherName: z.string(),
    problemId: publicIdSchema,
    problemNumber: z.string(),
    problemTitle: z.string(),
    groupName: z.string(),
    comment: z.string(),
    isLatestReview: z.boolean(),
  })
  .strict()
export const reviewHistoryResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(reviewHistoryItemSchema),
    nextCursor: publicIdSchema.nullable(),
    options: z
      .object({
        courses: z.array(named),
        courseId: publicIdSchema.nullable(),
        lessons: z.array(z.number().int()),
        lesson: z.number().int().nullable(),
        students: z.array(z.object({ studentId: publicIdSchema, name: z.string() }).strict()),
        teachers: z.array(named),
        problems: z.array(named),
        canChooseTeacher: z.boolean(),
      })
      .strict(),
  })
  .strict()
export const reviewHistoryDetailResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    detail: z
      .object({
        review: reviewHistoryItemSchema,
        statement: z.string(),
        document: webContentDocumentSchema.nullable(),
        blockedBy: z.string().nullable(),
        verdictMode: z.enum([
          'verdict_plus_minus',
          'verdict_plus_minus_half',
          'verdict_plus_steps',
        ]),
        comment: z.string(),
        threadVersion: z.number().int().positive(),
        latestReviewId: publicIdSchema,
        entries: z.array(
          z
            .object({
              entryId: publicIdSchema,
              text: z.string().nullable(),
              attachments: z.array(
                z
                  .object({
                    attachmentId: publicIdSchema,
                    ordinal: z.number().int(),
                    annotation: reviewAnnotationManifestSchema.nullable(),
                  })
                  .strict(),
              ),
            })
            .strict(),
        ),
        timeline: z.array(
          z
            .object({
              reviewId: publicIdSchema,
              verdict: writtenReviewVerdictSchema,
              completedAt: z.iso.datetime(),
              teacherName: z.string(),
              comment: z.string(),
            })
            .strict(),
        ),
      })
      .strict(),
  })
  .strict()
export type ReviewHistoryResponse = z.infer<typeof reviewHistoryResponseSchema>
export type ReviewHistoryDetailResponse = z.infer<typeof reviewHistoryDetailResponseSchema>

import { z } from 'zod'
import { publicIdSchema } from './auth'
import { webContentDocumentSchema } from './content'
import { reviewAnnotationManifestSchema, writtenReviewVerdictSchema } from './review-queue'
import { studentResultEventSchema } from './student-results'

// docs/review-history.md: same archive events, with review-scoped media authorization.
export const reviewConversationEventSchema = studentResultEventSchema.extend({
  problemNumber: z.string(),
  internal: z.literal(false),
  attachments: z.array(
    studentResultEventSchema.shape.attachments.element.extend({
      url: z
        .string()
        .regex(
          /^\/staff\/api\/v1\/review\/history\/[a-z0-9._:-]+\/(?:attachments|legacy-attachments)\/[a-z0-9._:-]+$/,
        ),
    }),
  ),
})
export const reviewConversationResponseSchema = z.object({
  schemaVersion: z.literal(1),
  requestId: z.string(),
  events: z.array(reviewConversationEventSchema),
  nextCursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
})
export type ReviewConversationResponse = z.infer<typeof reviewConversationResponseSchema>

// Authoritative flow: docs/review-history.md.
const named = z.object({ id: publicIdSchema, name: z.string() }).strip()
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
  .strip()
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
        students: z.array(z.object({ studentId: publicIdSchema, name: z.string() }).strip()),
        teachers: z.array(named),
        problems: z.array(named),
        canChooseTeacher: z.boolean(),
      })
      .strip(),
  })
  .strip()
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
                  .strip(),
              ),
            })
            .strip(),
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
            .strip(),
        ),
      })
      .strip(),
  })
  .strip()
export type ReviewHistoryResponse = z.infer<typeof reviewHistoryResponseSchema>
export type ReviewHistoryDetailResponse = z.infer<typeof reviewHistoryDetailResponseSchema>

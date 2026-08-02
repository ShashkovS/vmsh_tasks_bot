import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const publicationStateSchema = z
  .object({
    state: z.enum(['none', 'scheduled', 'published']),
    scheduledAt: z.iso.datetime({ offset: true }).nullable(),
  })
  .strict()
  .superRefine((publication, context) => {
    if ((publication.state === 'scheduled') !== (publication.scheduledAt !== null)) {
      context.addIssue({
        code: 'custom',
        message: 'Only a scheduled publication has a scheduled time',
        path: ['scheduledAt'],
      })
    }
  })

export const staffDashboardLessonSchema = z
  .object({
    groupLessonId: publicIdSchema,
    lessonNumber: z.number().int().positive(),
    cycleAnchorDate: z.iso.date(),
    course: z
      .object({
        courseId: publicIdSchema,
        code: z.string().trim().min(1).max(32),
        name: z.string().trim().min(1).max(160),
      })
      .strict(),
    group: z
      .object({
        groupId: publicIdSchema,
        code: z.string().trim().min(1).max(16),
        name: z.string().trim().min(1).max(160),
        colorKey: z.string().trim().min(1).max(32),
      })
      .strict(),
    phase: z.enum([
      'draft',
      'scheduled',
      'active',
      'hints_published',
      'submissions_closed',
      'solutions_published',
    ]),
    publications: z
      .object({
        condition: publicationStateSchema,
        hint: publicationStateSchema,
        solution: publicationStateSchema,
      })
      .strict(),
    oral: z
      .object({
        openWindows: z.number().int().nonnegative(),
        upcomingWindows: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .strict()

const deliverySummarySchema = z
  .object({
    failedBatches: z.number().int().nonnegative(),
    failedRecipients: z.number().int().nonnegative(),
  })
  .strict()

export const staffDashboardResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    generatedAt: z.iso.datetime({ offset: true }),
    summary: z
      .object({
        review: z
          .object({
            totalCases: z.number().int().nonnegative(),
            claimedByOthers: z.number().int().nonnegative(),
          })
          .strict(),
        questions: z
          .object({
            awaitingStaff: z.number().int().nonnegative(),
            olderThanOneHour: z.number().int().nonnegative(),
          })
          .strict(),
        publications: z
          .object({
            conditionsPublished: z.number().int().nonnegative(),
            groupLessons: z.number().int().nonnegative(),
          })
          .strict(),
        oral: z
          .object({
            openWindows: z.number().int().nonnegative(),
            upcomingWindows: z.number().int().nonnegative(),
          })
          .strict(),
        delivery: deliverySummarySchema.nullable(),
      })
      .strict(),
    lessons: z.array(staffDashboardLessonSchema).max(500),
    requestId: z.string().trim().min(1).max(128),
  })
  .strict()
  .superRefine((dashboard, context) => {
    if (dashboard.summary.review.claimedByOthers > dashboard.summary.review.totalCases) {
      context.addIssue({
        code: 'custom',
        message: 'Claimed cases cannot exceed all cases',
        path: ['summary', 'review', 'claimedByOthers'],
      })
    }
    if (dashboard.summary.questions.olderThanOneHour > dashboard.summary.questions.awaitingStaff) {
      context.addIssue({
        code: 'custom',
        message: 'Old questions cannot exceed all questions',
        path: ['summary', 'questions', 'olderThanOneHour'],
      })
    }
    if (dashboard.summary.publications.groupLessons !== dashboard.lessons.length) {
      context.addIssue({
        code: 'custom',
        message: 'Lesson count must match the projection',
        path: ['summary', 'publications', 'groupLessons'],
      })
    }
  })

export type StaffDashboardResponse = z.infer<typeof staffDashboardResponseSchema>
export type StaffDashboardLesson = z.infer<typeof staffDashboardLessonSchema>

export const staffDashboardQueryKey = (principal: PrincipalQueryScope) =>
  [...principalQueryKey(principal), 'staff-dashboard'] as const

import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const progressCountsSchema = z
  .object({
    attempted: z.number().int().nonnegative(),
    accepted: z.number().int().nonnegative(),
    partial: z.number().int().nonnegative(),
    needsWork: z.number().int().nonnegative(),
    awaitingReview: z.number().int().nonnegative(),
  })
  .strip()
  .refine(
    (value) =>
      value.accepted + value.partial + value.needsWork <= value.attempted &&
      value.awaitingReview <= value.attempted,
    { message: 'Progress counters cannot exceed attempted' },
  )

const courseAnalyticsLessonSchema = z
  .object({
    lessonNumber: z.number().int().nonnegative(),
    groupId: publicIdSchema,
    groupCode: z.string().trim().min(1).max(20),
    simpleStrength: z.number().min(0).max(10),
    complexStrength: z.number().min(0).max(10),
    maxComplexStrength: z.number().min(0).max(10),
    solvedItems: z.number().int().nonnegative(),
    totalItems: z.number().int().nonnegative(),
  })
  .strip()
  .refine(
    (value) =>
      value.complexStrength <= value.maxComplexStrength && value.solvedItems <= value.totalItems,
    { message: 'Course analytics counters or strengths are inconsistent' },
  )

export const courseProgressResponseSchema = z
  .object({
    courseId: publicIdSchema,
    summary: progressCountsSchema,
    lessons: z.array(
      progressCountsSchema.extend({ lessonNumber: z.number().int().nonnegative() }).strip(),
    ),
    activity: z.array(
      z
        .object({
          date: z.iso.date(),
          problemCount: z.number().int().positive(),
        })
        .strip(),
    ),
    analytics: z
      .object({
        runId: publicIdSchema,
        algorithmVersion: z.string().trim().min(1).max(100),
        calculatedAt: z.iso.datetime({ offset: true }),
        lessons: z.array(courseAnalyticsLessonSchema),
      })
      .strip()
      .nullable(),
    achievements: z.array(
      z
        .object({
          code: z.string().regex(/^[a-z][a-z0-9_]{0,63}$/),
          earnedAt: z.iso.datetime({ offset: true }),
        })
        .strip(),
    ),
  })
  .strip()
  .superRefine((response, context) => {
    const lessonNumbers = new Set<number>()
    response.lessons.forEach((lesson, index) => {
      if (lessonNumbers.has(lesson.lessonNumber)) {
        context.addIssue({
          code: 'custom',
          message: 'Lesson progress rows must be unique',
          path: ['lessons', index, 'lessonNumber'],
        })
      }
      lessonNumbers.add(lesson.lessonNumber)
    })
    const dates = new Set<string>()
    response.activity.forEach((day, index) => {
      if (dates.has(day.date)) {
        context.addIssue({
          code: 'custom',
          message: 'Activity dates must be unique',
          path: ['activity', index, 'date'],
        })
      }
      dates.add(day.date)
    })
    const analyticsLessons = new Set<number>()
    response.analytics?.lessons.forEach((lesson, index) => {
      if (analyticsLessons.has(lesson.lessonNumber)) {
        context.addIssue({
          code: 'custom',
          message: 'Course analytics lesson rows must be unique',
          path: ['analytics', 'lessons', index, 'lessonNumber'],
        })
      }
      analyticsLessons.add(lesson.lessonNumber)
    })
    const achievementCodes = new Set<string>()
    response.achievements.forEach((achievement, index) => {
      if (achievementCodes.has(achievement.code)) {
        context.addIssue({
          code: 'custom',
          message: 'Course achievements must be unique',
          path: ['achievements', index, 'code'],
        })
      }
      achievementCodes.add(achievement.code)
    })
  })
export type CourseProgressResponse = z.infer<typeof courseProgressResponseSchema>

export const progressQueryKey = (principal: PrincipalQueryScope, courseId: string) =>
  [...principalQueryKey(principal), 'course-progress', publicIdSchema.parse(courseId)] as const

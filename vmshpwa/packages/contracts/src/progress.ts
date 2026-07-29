import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const progressCountsSchema = z
  .object({
    attempted: z.number().int().nonnegative(),
    accepted: z.number().int().nonnegative(),
    partial: z.number().int().nonnegative(),
    needsWork: z.number().int().nonnegative(),
  })
  .strip()
  .refine((value) => value.accepted + value.partial + value.needsWork === value.attempted, {
    message: 'Progress categories must add up to attempted',
  })

export const courseProgressResponseSchema = z
  .object({
    courseId: publicIdSchema,
    summary: progressCountsSchema,
    lessons: z.array(
      progressCountsSchema.extend({ lessonNumber: z.number().int().positive() }).strip(),
    ),
    activity: z.array(
      z
        .object({
          date: z.iso.date(),
          problemCount: z.number().int().positive(),
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
  })
export type CourseProgressResponse = z.infer<typeof courseProgressResponseSchema>

export const progressQueryKey = (principal: PrincipalQueryScope, courseId: string) =>
  [...principalQueryKey(principal), 'course-progress', publicIdSchema.parse(courseId)] as const

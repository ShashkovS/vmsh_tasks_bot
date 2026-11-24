import { z } from 'zod'
import { publicIdSchema } from './auth'

/** Personal PWA contribution; docs/review-contribution.md. */
const count = z.number().int().nonnegative()
const counts = z.object({ total: count, plus: count }).refine((v) => v.plus <= v.total)
const totals = z
  .object({
    total: count,
    plus: count,
    byKind: z.object({ written: counts, school: counts, zoom: counts }),
  })
  .refine((v) => v.plus <= v.total)
const milestone = z.object({ value: count, reached: z.array(count), next: count })
const streak = z.object({
  current: count,
  best: count,
  periodCount: count,
  minimum: z.literal(3),
  milestone,
})
export const reviewContributionQuerySchema = z
  .object({
    course: publicIdSchema.optional(),
    lesson: z.number().int().nonnegative().max(999999).optional(),
    groupLesson: publicIdSchema.optional(),
  })
  .strict()
export const reviewContributionSchema = z.object({
  schemaVersion: z.literal(1),
  requestId: z.string(),
  timezone: z.literal('Europe/Moscow'),
  allTime: totals,
  lesson: z
    .object({
      courseId: publicIdSchema,
      number: count,
      counts: totals,
      milestone,
    })
    .nullable(),
  milestone,
  daily: streak,
  weekly: streak,
  courses: z.array(z.object({ id: publicIdSchema, name: z.string(), lessons: z.array(count) })),
})
export type ReviewContributionQuery = z.infer<typeof reviewContributionQuerySchema>
export type ReviewContribution = z.infer<typeof reviewContributionSchema>

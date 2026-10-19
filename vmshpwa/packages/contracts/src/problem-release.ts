import { z } from 'zod'
import { publicIdSchema } from './auth'

/** Whole-condition controls; docs/problem-release.md and StaffProblemReleasePreview. */
export const problemReleaseChangeSchema = z
  .object({
    sourceOrdinal: z.number().int().nonnegative(),
    isOpen: z.boolean(),
  })
  .strict()
export const problemReleaseResponseSchema = z
  .object({
    groupLessonId: publicIdSchema,
    conditionRevisionId: publicIdSchema,
    version: z.number().int().positive(),
    etag: z.string().min(1),
    editable: z.boolean(),
    problems: z.array(problemReleaseChangeSchema).max(2000),
  })
  .strip()
export const problemReleaseRequestSchema = z
  .object({
    conditionRevisionId: publicIdSchema,
    changes: z.array(problemReleaseChangeSchema).min(1).max(2000),
  })
  .strict()
  .superRefine((input, context) => {
    if (new Set(input.changes.map((item) => item.sourceOrdinal)).size !== input.changes.length) {
      context.addIssue({ code: 'custom', message: 'Duplicate task ordinal', path: ['changes'] })
    }
  })
export type ProblemReleaseResponse = z.infer<typeof problemReleaseResponseSchema>
export type ProblemReleaseRequest = z.infer<typeof problemReleaseRequestSchema>

import { z } from 'zod'
import { publicIdSchema } from './auth'

// Admin operation lifecycle; docs/lesson-statistics.md.
export const statisticsRecalculationRequestSchema = z.object({
  courseId: publicIdSchema,
  idempotencyKey: publicIdSchema,
})
export const statisticsRecalculationSchema = z.object({
  busy: z.boolean(),
  operation: z
    .object({
      operationId: publicIdSchema,
      state: z.enum(['running', 'completed', 'failed']),
      startedAt: z.iso.datetime(),
      completedAt: z.iso.datetime().nullable(),
      runId: publicIdSchema.nullable(),
      errorCode: z.string().nullable(),
    })
    .nullable(),
})

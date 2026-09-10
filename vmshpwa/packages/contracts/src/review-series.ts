import { z } from 'zod'
import { publicIdSchema } from './auth'
import { webContentDocumentSchema } from './content'

export const reviewSeriesHistorySchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(z.object({ reviewId: publicIdSchema, materialKey: z.string() }).strict()),
    nextCursor: publicIdSchema.nullable(),
  })
  .strict()
export const reviewSeriesConditionSchema = z
  .object({
    schemaVersion: z.literal(1),
    label: z.string(),
    document: webContentDocumentSchema.nullable(),
  })
  .strict()
export type ReviewSeriesHistory = z.infer<typeof reviewSeriesHistorySchema>
export type ReviewSeriesCondition = z.infer<typeof reviewSeriesConditionSchema>

/** Whole-entry routing, docs/serial-review-feed.md. */
export const reviewTransferPreviewSchema = z
  .object({
    schemaVersion: z.literal(1),
    entryId: publicIdSchema,
    sourceVersion: z.number().int().positive(),
    entryVersion: z.number().int().positive(),
    studentName: z.string(),
    sourceLabel: z.string(),
    photoCount: z.number().int().nonnegative(),
    targets: z.array(
      z
        .object({
          problemId: publicIdSchema,
          label: z.string(),
          threadVersion: z.number().int().nonnegative(),
          threadId: publicIdSchema.nullable(),
        })
        .strict(),
    ),
  })
  .strict()
export const reviewTransferRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    entryId: publicIdSchema,
    claimToken: publicIdSchema,
    targetProblemId: publicIdSchema,
    sourceVersion: z.number().int().positive(),
    entryVersion: z.number().int().positive(),
    targetVersion: z.number().int().nonnegative(),
    targetThreadId: publicIdSchema.nullable(),
    mode: z.enum(['move', 'clone']),
    idempotencyKey: publicIdSchema,
  })
  .strict()
export const reviewTransferResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    mode: z.enum(['move', 'clone']),
    sourceEntryId: publicIdSchema,
    targetEntryId: publicIdSchema,
    targetProblemId: publicIdSchema,
    targetLabel: z.string(),
  })
  .strict()
export type ReviewTransferPreview = z.infer<typeof reviewTransferPreviewSchema>
export type ReviewTransferRequest = z.infer<typeof reviewTransferRequestSchema>
export type ReviewTransferResponse = z.infer<typeof reviewTransferResponseSchema>

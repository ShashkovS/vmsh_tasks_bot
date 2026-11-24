import { z } from 'zod'
import { publicIdSchema } from './auth'

/** Private Staff-only proposals; docs/ai-review-assistant.md. */
export const aiReviewSuggestionSchema = z.object({
  suggestionId: publicIdSchema,
  snapshot: z.string().regex(/^[a-f0-9]{64}$/),
  comment: z.string().max(100_000).nullable(),
  verdict: z.number().int().min(11).max(17).nullable(),
  analysis: z.string().max(100_000).nullable(),
  source: z.string().min(1).max(200),
  model: z.string().max(200).nullable(),
  createdAt: z.iso.datetime(),
  isCurrent: z.boolean(),
})
export type AiReviewSuggestion = z.infer<typeof aiReviewSuggestionSchema>

export const aiReviewSuggestionsSchema = z.object({
  caseId: publicIdSchema,
  snapshot: z.string().regex(/^[a-f0-9]{64}$/),
  evidenceKey: z.string(),
  pending: z.boolean(),
  items: z.array(aiReviewSuggestionSchema).max(50),
  nextCursor: z.string().nullable(),
})
export const aiReviewTokensSchema = z.object({
  items: z.array(
    z.object({
      tokenId: publicIdSchema,
      name: z.string(),
      createdAt: z.iso.datetime(),
      expiresAt: z.iso.datetime(),
      revokedAt: z.iso.datetime().nullable(),
    }),
  ),
})
export const aiReviewTokenReceiptSchema = z.object({
  tokenId: publicIdSchema,
  secret: z.string().regex(/^air_[A-Za-z0-9_-]{43}$/),
  expiresAt: z.iso.datetime(),
})

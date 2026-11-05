import { expect, it } from 'vitest'
import {
  reviewSheetSearchSchema,
  reviewSheetCompleteRequestSchema,
  reviewSheetConversationSchema,
} from './review-sheet'

it('defaults to pending and validates shareable sheet selection', () => {
  expect(reviewSheetSearchSchema.parse({})).toEqual({ mode: 'pending' })
  expect(reviewSheetSearchSchema.parse({ lesson: 'gl-1', mode: 'all' })).toEqual({
    lesson: 'gl-1',
    mode: 'all',
  })
  expect(reviewSheetSearchSchema.parse({ mode: 'bad', lesson: '../foreign' })).toEqual({
    mode: 'pending',
    lesson: undefined,
  })
})
it('requires optimistic snapshot and rejects lease fields on sheet completion', () => {
  const request = {
    schemaVersion: 1,
    snapshot: 'a'.repeat(64),
    idempotencyKey: 'sheet-1',
    verdict: 17,
    comment: null,
    confirmWithoutComment: false,
    annotations: [],
    internalReactionId: null,
  }
  expect(reviewSheetCompleteRequestSchema.safeParse(request).success).toBe(true)
  expect(
    reviewSheetCompleteRequestSchema.safeParse({ ...request, claimToken: 'claim' }).success,
  ).toBe(false)
  expect(reviewSheetCompleteRequestSchema.safeParse({ ...request, snapshot: 'bad' }).success).toBe(
    false,
  )
})
it('validates paged sheet conversations without weakening the archive contract', () => {
  expect(
    reviewSheetConversationSchema.parse({
      schemaVersion: 1,
      requestId: 'r',
      events: [],
      nextCursor: null,
      total: 0,
    }).events,
  ).toEqual([])
})

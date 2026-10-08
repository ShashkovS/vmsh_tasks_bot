import { z } from 'zod'

import {
  publicIdSchema,
  reviewAnnotationManifestSchema,
  writtenTeacherReactionIdSchema,
  type BrowserStorageNamespace,
  type ReviewLease,
} from '@vmsh/contracts'

/**
 * Reload-safe Teacher work for development-plan Phase 6. The server lease is
 * deliberately not stored: only the exact evidence fingerprint may restore a
 * comment, verdict, reaction and future photo annotations.
 */
export const reviewDraftSchema = z
  .object({
    schemaVersion: z.literal(1),
    logicalCaseId: publicIdSchema,
    evidenceFingerprint: z.string().min(1).max(16_384),
    idempotencyKey: publicIdSchema,
    verdictValue: z.string().trim().min(1).nullable(),
    comment: z.string().max(100_000),
    reactionId: writtenTeacherReactionIdSchema.nullable(),
    annotations: z.array(reviewAnnotationManifestSchema).max(10),
    updatedAt: z.iso.datetime(),
  })
  .strict()

export type ReviewDraft = z.infer<typeof reviewDraftSchema>

export interface ReviewDraftStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export function createReviewEvidenceFingerprint(lease: ReviewLease): string {
  return lease.evidenceBranches
    .map((branch) => {
      if (!branch.thread) return `${branch.queueId}:legacy`
      const entries = branch.thread.entries
        .map((entry) => `${entry.entryId}@${entry.entryVersion}`)
        .join(',')
      return `${branch.queueId}:${branch.thread.threadId}@${branch.thread.threadVersion}:${entries}`
    })
    .join('|')
}

function shortStableHash(value: string): string {
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash = Math.imul(hash ^ value.charCodeAt(index), 0x01000193)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

export function reviewDraftStorageKey(
  namespace: BrowserStorageNamespace,
  accountId: string,
  logicalCaseId: string,
  evidenceFingerprint: string,
): string {
  return `${namespace}:review-draft:${accountId}:${logicalCaseId}:${shortStableHash(evidenceFingerprint)}`
}

export function createEmptyReviewDraft(
  logicalCaseId: string,
  evidenceFingerprint: string,
  options: { idempotencyKey?: string; now?: Date } = {},
): ReviewDraft {
  return reviewDraftSchema.parse({
    schemaVersion: 1,
    logicalCaseId,
    evidenceFingerprint,
    idempotencyKey: options.idempotencyKey ?? `review-complete-${crypto.randomUUID()}`,
    verdictValue: null,
    comment: '',
    reactionId: null,
    annotations: [],
    updatedAt: (options.now ?? new Date()).toISOString(),
  })
}

export function readReviewDraft(
  storage: ReviewDraftStorage,
  key: string,
  expected: { logicalCaseId: string; evidenceFingerprint: string },
): ReviewDraft | null {
  try {
    const serialized = storage.getItem(key)
    if (serialized === null) return null
    const parsed = reviewDraftSchema.safeParse(JSON.parse(serialized))
    if (
      !parsed.success ||
      parsed.data.logicalCaseId !== expected.logicalCaseId ||
      parsed.data.evidenceFingerprint !== expected.evidenceFingerprint
    ) {
      storage.removeItem(key)
      return null
    }
    return parsed.data
  } catch {
    try {
      storage.removeItem(key)
    } catch {
      // A denied storage remains unavailable; the page reports this explicitly.
    }
    return null
  }
}

export function writeReviewDraft(
  storage: ReviewDraftStorage,
  key: string,
  draft: ReviewDraft,
): boolean {
  try {
    storage.setItem(key, JSON.stringify(reviewDraftSchema.parse(draft)))
    return true
  } catch {
    return false
  }
}

export function clearReviewDraft(storage: ReviewDraftStorage, key: string): boolean {
  try {
    storage.removeItem(key)
    return true
  } catch {
    return false
  }
}

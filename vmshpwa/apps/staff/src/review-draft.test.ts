import { describe, expect, it } from 'vitest'

import { browserStorageNamespaceSchema, reviewLeaseSchema } from '@vmsh/contracts'

import {
  clearReviewDraft,
  createEmptyReviewDraft,
  createReviewEvidenceFingerprint,
  readReviewDraft,
  reviewDraftStorageKey,
  writeReviewDraft,
  type ReviewDraftStorage,
} from './review-draft'

class MemoryStorage implements ReviewDraftStorage {
  readonly values = new Map<string, string>()

  getItem(key: string) {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string) {
    this.values.set(key, value)
  }

  removeItem(key: string) {
    this.values.delete(key)
  }
}

const namespace = browserStorageNamespaceSchema.parse('vmsh-179:v1:staff:agent')
const lease = reviewLeaseSchema.parse({
  claimToken: 'review-claim-one',
  logicalCaseId: 'synonym-one',
  student: { studentId: 'student-one', displayName: 'Анна Белова' },
  claimedAt: '2026-10-04T12:00:00Z',
  expiresAt: '2026-10-04T12:30:00Z',
  branches: [
    {
      queueId: 'queue-one',
      problemId: 'problem-one',
      problemNumber: '41н.1',
      problemTitle: 'Задача',
      courseId: 'course-one',
      courseName: 'Математика',
      groupId: 'group-one',
      groupName: 'Начинающие',
      groupShortCode: 'н',
      groupColorKey: 'level-1',
      submittedAt: '2026-10-04T11:59:00Z',
      leaseVersion: 1,
    },
  ],
  evidenceBranches: [
    {
      queueId: 'queue-one',
      thread: {
        threadId: 'thread-one',
        threadVersion: 3,
        entries: [
          {
            entryId: 'entry-one',
            entryVersion: 2,
            entryKind: 'submission',
            text: 'Решение',
            submittedAt: '2026-10-04T11:59:00Z',
            attachments: [],
          },
        ],
        timelineEntries: [],
      },
    },
  ],
})

describe('Staff review draft persistence', () => {
  it('restores only the same account, logical case and evidence boundary', () => {
    const storage = new MemoryStorage()
    const fingerprint = createReviewEvidenceFingerprint(lease)
    const key = reviewDraftStorageKey(namespace, 'staff-one', lease.logicalCaseId, fingerprint)
    const draft = {
      ...createEmptyReviewDraft(lease.logicalCaseId, fingerprint, {
        idempotencyKey: 'review-complete-one',
        now: new Date('2026-10-04T12:01:00Z'),
      }),
      comment: 'Не потерять этот комментарий.',
      verdictValue: 'plus-minus',
      reactionId: 100 as const,
    }

    expect(writeReviewDraft(storage, key, draft)).toBe(true)
    expect(
      readReviewDraft(storage, key, {
        logicalCaseId: lease.logicalCaseId,
        evidenceFingerprint: fingerprint,
      }),
    ).toEqual(draft)
    expect(
      reviewDraftStorageKey(namespace, 'staff-two', lease.logicalCaseId, fingerprint),
    ).not.toBe(key)
  })

  it('rejects corrupt or stale evidence without touching another draft', () => {
    const storage = new MemoryStorage()
    const fingerprint = createReviewEvidenceFingerprint(lease)
    const key = reviewDraftStorageKey(namespace, 'staff-one', lease.logicalCaseId, fingerprint)
    const otherKey = `${key}:other`
    storage.setItem(key, '{bad json')
    storage.setItem(otherKey, 'keep')

    expect(
      readReviewDraft(storage, key, {
        logicalCaseId: lease.logicalCaseId,
        evidenceFingerprint: fingerprint,
      }),
    ).toBeNull()
    expect(storage.getItem(otherKey)).toBe('keep')

    const draft = createEmptyReviewDraft(lease.logicalCaseId, fingerprint, {
      idempotencyKey: 'review-complete-two',
    })
    writeReviewDraft(storage, key, draft)
    expect(
      readReviewDraft(storage, key, {
        logicalCaseId: lease.logicalCaseId,
        evidenceFingerprint: `${fingerprint}:changed`,
      }),
    ).toBeNull()
  })

  it('clears only after the caller explicitly confirms success', () => {
    const storage = new MemoryStorage()
    const key = 'review-draft'
    storage.setItem(key, 'work')
    expect(clearReviewDraft(storage, key)).toBe(true)
    expect(storage.getItem(key)).toBeNull()
  })
})

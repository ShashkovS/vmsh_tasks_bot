import { describe, expect, it } from 'vitest'

import writtenThreadFixture from '../../../packages/contracts/fixtures/submissions/written-thread.v1.json'
import { writtenThreadSchema, type WrittenEntry, type WrittenThread } from '@vmsh/contracts'

import { buildWrittenChatItems, replaceableWrittenEntry } from './student-written-chat'

const fixtureThread = writtenThreadSchema.parse(writtenThreadFixture.threadResponse.thread)
const studentEntry = fixtureThread.entries[0]!

function entry(overrides: Partial<WrittenEntry> & { entryId: string }): WrittenEntry {
  return { ...studentEntry, attachments: [], ...overrides }
}

function teacherComment(entryId: string, at: string): WrittenEntry {
  return entry({
    entryId,
    authorKind: 'teacher',
    entryKind: 'teacher_comment',
    problemRevision: null,
    text: 'Неплохо!',
    serverReceivedAt: at,
  })
}

function review(overrides: Partial<WrittenThread['reviews'][number]> = {}) {
  return {
    reviewId: 'written-review-1',
    targetProblemId: studentEntry.problemRevision!.conditionRevisionId,
    verdict: 14,
    commentEntryId: null,
    comment: 'Неплохо!',
    reviewerName: 'ВМШ 179 Администратор',
    source: 'staff' as const,
    evidenceEntryIds: [studentEntry.entryId],
    annotations: [],
    studentReaction: null,
    completedAt: '2026-09-20T15:00:00.000000Z',
    ...overrides,
  }
}

function thread(entries: WrittenEntry[], reviews: WrittenThread['reviews']): WrittenThread {
  return writtenThreadSchema.parse({
    ...fixtureThread,
    entries,
    reviews,
    latestEntryAt: entries.at(-1)?.serverReceivedAt ?? fixtureThread.latestEntryAt,
  })
}

describe('Student written thread as one conversation', () => {
  it('folds a review into the teacher comment it was written with', () => {
    const comment = teacherComment('written-entry-comment', '2026-09-20T15:00:00.000000Z')
    const items = buildWrittenChatItems(
      thread(
        [studentEntry, comment],
        [review({ commentEntryId: comment.entryId })],
      ),
    )
    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({ key: `entry:${studentEntry.entryId}`, review: null })
    expect(items[1]?.entry?.entryId).toBe(comment.entryId)
    expect(items[1]?.review?.reviewId).toBe('written-review-1')
  })

  it('shows a review of its own when it carries no comment entry', () => {
    const items = buildWrittenChatItems(thread([studentEntry], [review()]))
    expect(items.map((item) => item.key)).toEqual([
      `entry:${studentEntry.entryId}`,
      'review:written-review-1',
    ])
    expect(items[1]?.entry).toBeNull()
  })

  it('orders the conversation by time, whatever the server listed first', () => {
    const later = entry({
      entryId: 'written-entry-later',
      serverReceivedAt: '2026-09-20T18:00:00.000000Z',
    })
    const items = buildWrittenChatItems(
      thread([studentEntry, later], [review({ completedAt: '2026-09-20T15:00:00.000000Z' })]),
    )
    expect(items.map((item) => item.at)).toEqual([
      studentEntry.serverReceivedAt,
      '2026-09-20T15:00:00.000000Z',
      later.serverReceivedAt,
    ])
  })

  it('keeps drafts and deleted material out of the conversation', () => {
    const hidden = entry({ entryId: 'written-entry-draft', state: 'draft', text: 'черновик' })
    const items = buildWrittenChatItems(thread([studentEntry, hidden], []))
    expect(items.map((item) => item.key)).toEqual([`entry:${studentEntry.entryId}`])
  })

  it('offers a replacement only for the last submitted own message', () => {
    const later = entry({
      entryId: 'written-entry-later',
      serverReceivedAt: '2026-09-20T18:00:00.000000Z',
    })
    expect(replaceableWrittenEntry(thread([studentEntry, later], []))?.entryId).toBe(later.entryId)
    expect(
      replaceableWrittenEntry(thread([teacherComment('written-entry-c', studentEntry.serverReceivedAt)], [])),
    ).toBeNull()
    expect(replaceableWrittenEntry(null)).toBeNull()
  })
})

import type { WrittenEntry, WrittenReviewProjection, WrittenThread } from '@vmsh/contracts'

/**
 * Written thread as one conversation. The server keeps material entries and
 * review results apart; the Student reads a single chronological dialogue, so
 * a review is folded into the teacher comment it was written with and only
 * stands alone when it has no comment entry of its own.
 * See `dev/development-plan/09-phase-5-written-submissions.md`.
 */
export interface WrittenChatItem {
  key: string
  at: string
  entry: WrittenEntry | null
  review: WrittenReviewProjection | null
}

/** Drafts and uploads are local state; a deleted entry is not part of the talk. */
function isVisibleEntry(entry: WrittenEntry): boolean {
  return entry.state === 'submitted' || entry.state === 'locked'
}

export function buildWrittenChatItems(thread: WrittenThread | null): WrittenChatItem[] {
  if (!thread) return []
  const visible = thread.entries.filter(isVisibleEntry)
  const visibleIds = new Set(visible.map((entry) => entry.entryId))
  const reviewByEntry = new Map<string, WrittenReviewProjection>()
  for (const review of thread.reviews) {
    if (review.commentEntryId && visibleIds.has(review.commentEntryId)) {
      reviewByEntry.set(review.commentEntryId, review)
    }
  }
  const items: WrittenChatItem[] = [
    ...visible.map((entry) => ({
      key: `entry:${entry.entryId}`,
      at: entry.serverReceivedAt,
      entry,
      review: reviewByEntry.get(entry.entryId) ?? null,
    })),
    ...thread.reviews
      .filter((review) => !review.commentEntryId || !visibleIds.has(review.commentEntryId))
      .map((review) => ({
        key: `review:${review.reviewId}`,
        at: review.completedAt,
        entry: null,
        review,
      })),
  ]
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) =>
      left.item.at === right.item.at
        ? left.index - right.index
        : left.item.at < right.item.at
          ? -1
          : 1,
    )
    .map(({ item }) => item)
}

/** The last own message a replacement may still target. */
export function replaceableWrittenEntry(thread: WrittenThread | null): WrittenEntry | null {
  if (!thread) return null
  return (
    [...thread.entries]
      .reverse()
      .find(
        (entry) =>
          entry.authorKind === 'student' &&
          entry.entryKind === 'submission' &&
          entry.state === 'submitted',
      ) ?? null
  )
}

const timeFormat = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const dateFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })

export function chatTime(value: string): string {
  return timeFormat.format(new Date(value))
}

export function chatDate(value: string): string {
  return dateFormat.format(new Date(value))
}

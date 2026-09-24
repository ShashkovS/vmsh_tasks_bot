import type { ReviewQueueItem } from '@vmsh/contracts'
import type { ReviewQueueClient } from '@vmsh/app-shell'

/** Serial review decisions: docs/serial-review.md; used by queue and series page. */
export async function allReviewItems(
  client: Pick<ReviewQueueClient, 'list'>,
  signal?: AbortSignal,
) {
  const items: ReviewQueueItem[] = []
  let cursor: string | undefined
  do {
    const page = await client.list(cursor ? { cursor } : {}, signal ? { signal } : {})
    items.push(...page.items)
    cursor = page.nextCursor ?? undefined
  } while (cursor)
  return items
}

export function reviewProblemGroups(items: ReviewQueueItem[]) {
  const groups = new Map<
    string,
    { problem: ReviewQueueItem['branches'][number]; items: ReviewQueueItem[]; oldest: string }
  >()
  for (const item of items) {
    for (const problem of item.branches) {
      const group = groups.get(problem.problemId) ?? {
        problem,
        items: [],
        oldest: item.submittedAt,
      }
      if (!group.items.some((other) => other.logicalCaseId === item.logicalCaseId))
        group.items.push(item)
      if (item.submittedAt < group.oldest) group.oldest = item.submittedAt
      groups.set(problem.problemId, group)
    }
  }
  return [...groups.values()].sort((a, b) => a.oldest.localeCompare(b.oldest))
}

export function seriesCandidates(
  items: ReviewQueueItem[],
  problemId: string,
  excluded: Set<string>,
  random = Math.random,
) {
  const available = items.filter(
    (item) =>
      item.branches.some((branch) => branch.problemId === problemId) &&
      !excluded.has(item.logicalCaseId) &&
      (!item.lock || item.lock.isOwnedByCurrentStaff),
  )
  // Shuffle a small oldest window so simultaneous reviewers do not all claim its head.
  const window = available.splice(0, 5)
  for (let i = window.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[window[i], window[j]] = [window[j]!, window[i]!]
  }
  return [...window, ...available]
}

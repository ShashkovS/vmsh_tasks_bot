import { t } from '@lingui/core/macro'
import { z } from 'zod'
import type { ReviewQueueItem } from '@vmsh/contracts'
import { reviewProblemGroups } from './review-series-model'

// Queue presentation only; claim identities stay intact. See docs/serial-review.md
// and dev/design-system/05-pages-and-flows.md (Staff review).
export const reviewQueueSearchSchema = z.object({
  queueCourse: z.string().optional().catch(undefined),
  queueGroup: z.string().optional().catch(undefined),
  queueView: z.enum(['problems', 'works']).optional().catch(undefined),
  queueSort: z.enum(['waiting', 'count']).optional().catch(undefined),
  queueTableSort: z.enum(['task', 'waiting', 'group', 'student']).optional().catch(undefined),
})
export type ReviewQueueSearch = z.infer<typeof reviewQueueSearchSchema>
type Branch = ReviewQueueItem['branches'][number]
export const queueCourseKey = (branch: Branch) =>
  branch.courseId ?? `legacy:${branch.courseName ?? ''}`
export const queueGroupKey = (branch: Branch) =>
  branch.groupId ?? `legacy:${queueCourseKey(branch)}:${branch.groupShortCode}`

export function queueOptions(items: ReviewQueueItem[], course?: string) {
  const branches = items.flatMap((item) => item.branches)
  const options = (pairs: [string, string][]) =>
    [...new Map(pairs)]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  return {
    courses: options(branches.map((b) => [queueCourseKey(b), b.courseName ?? t`Без курса`])),
    groups: options(
      branches
        .filter((b) => !course || queueCourseKey(b) === course)
        .map((b) => [
          queueGroupKey(b),
          course ? b.groupName : `${b.groupName} · ${b.courseName ?? t`Без курса`}`,
        ]),
    ),
  }
}

export function filterReviewQueue(items: ReviewQueueItem[], search: ReviewQueueSearch) {
  const unique = new Map<string, ReviewQueueItem>()
  for (const item of items) {
    const branches = item.branches.filter(
      (b) =>
        (!search.queueCourse || queueCourseKey(b) === search.queueCourse) &&
        (!search.queueGroup || queueGroupKey(b) === search.queueGroup),
    )
    // This is a display projection, never an API payload: queueId still refers
    // to the original logical case, even when its first branch is filtered out.
    if (branches.length && !unique.has(item.queueId))
      unique.set(item.queueId, { ...item, branches })
  }
  return [...unique.values()]
}

export function reviewQueueCounts(items: ReviewQueueItem[]) {
  // logicalCaseId identifies the task/synonym group shared by students, while
  // queueId anchors one student's work; see docs/serial-review.md.
  const unique = [...new Map(items.map((item) => [item.queueId, item])).values()]
  const busy = unique.filter((item) => item.lock && !item.lock.isOwnedByCurrentStaff).length
  return { total: unique.length, available: unique.length - busy, busy }
}

export function sortedReviewProblems(
  items: ReviewQueueItem[],
  sort: ReviewQueueSearch['queueSort'],
) {
  return reviewProblemGroups(items).sort(
    (a, b) =>
      (sort === 'count' ? b.items.length - a.items.length : 0) ||
      a.oldest.localeCompare(b.oldest) ||
      a.problem.problemId.localeCompare(b.problem.problemId),
  )
}

export function workCount(count: number) {
  const last = count % 10,
    hundred = count % 100
  return `${count} ${last === 1 && hundred !== 11 ? t`работа` : last >= 2 && last <= 4 && (hundred < 12 || hundred > 14) ? t`работы` : t`работ`}`
}
export function formatReviewWaiting(minutes: number) {
  minutes = Math.max(0, Math.floor(minutes))
  if (minutes < 60) return t`${minutes} мин`
  const hours = Math.floor(minutes / 60)
  if (hours >= 24) return t`${Math.floor(hours / 24)} д${hours % 24 ? t` ${hours % 24} ч` : ''}`
  return t`${hours} ч${minutes % 60 ? t` ${minutes % 60} мин` : ''}`
}

import { describe, expect, it } from 'vitest'
import type { ReviewQueueItem } from '@vmsh/contracts'
import {
  filterReviewQueue,
  formatReviewWaiting,
  queueOptions,
  reviewQueueCounts,
  reviewQueueSearchSchema,
  sortedReviewProblems,
  workCount,
} from './review-queue-model'

function work(
  id: string,
  problemId = 'p-1',
  submittedAt = '2026-09-01T12:00:00Z',
): ReviewQueueItem {
  return {
    queueId: id,
    logicalCaseId: id,
    submittedAt,
    student: { studentId: 'u-1', displayName: 'Ученик' },
    lock: null,
    branches: [
      {
        queueId: id,
        problemId,
        submittedAt,
        problemNumber: '1н.1',
        problemTitle: 'Квадрат',
        courseId: 'c-1',
        courseName: 'Математика',
        groupId: 'g-1',
        groupName: 'Начинающие',
        groupShortCode: 'н',
        groupColorKey: null,
        leaseVersion: 0,
      },
    ],
  }
}

describe('queue summary and display filters (docs/serial-review.md)', () => {
  it('counts logical cases once, including owned leases as available', () => {
    const own = work('q-2'),
      other = work('q-3'),
      free = work('q-1')
    other.lock = {
      kind: 'pwa',
      teacher: { teacherId: 'u-2', displayName: 'Коллега' },
      expiresAt: '2026-09-30T12:00:00Z',
      isOwnedByCurrentStaff: false,
    }
    own.lock = { ...other.lock, isOwnedByCurrentStaff: true }
    free.branches.push({ ...free.branches[0]!, problemId: 'p-2' })
    expect(reviewQueueCounts([free, own, other, free])).toEqual({ total: 3, available: 2, busy: 1 })
    expect(reviewQueueCounts([other])).toEqual({ total: 1, available: 0, busy: 1 })
    expect(reviewQueueCounts([])).toEqual({ total: 0, available: 0, busy: 0 })
  })
  it('projects matching synonym branches without changing claim identity or source data', () => {
    const original = work('q-1')
    original.branches.push({
      ...original.branches[0]!,
      queueId: 'q-2',
      problemId: 'p-2',
      courseId: 'c-2',
      groupId: 'g-2',
      groupName: 'Эксперты',
    })
    const filtered = filterReviewQueue([original, original], {
      queueCourse: 'c-2',
      queueGroup: 'g-2',
    })
    expect(filtered).toHaveLength(1)
    expect(filtered[0]?.queueId).toBe('q-1')
    expect(filtered[0]?.branches.map((b) => b.problemId)).toEqual(['p-2'])
    expect(original.branches).toHaveLength(2)
    expect(filterReviewQueue([original], { queueCourse: 'c-1', queueGroup: 'g-2' })).toEqual([])
    expect(queueOptions([original], 'c-1').groups.map((g) => g.id)).toEqual(['g-1'])
    expect(queueOptions([original]).courses).toHaveLength(2)
  })
  it('sorts by work count then oldest work; default prioritizes waiting', () => {
    const items = [
      work('q-1', 'p-1'),
      work('q-2', 'p-2', '2026-09-02T00:00:00Z'),
      work('q-3', 'p-2'),
      work('q-4', 'p-3', '2026-08-30T00:00:00Z'),
      work('q-5', 'p-3'),
    ]
    expect(sortedReviewProblems(items, 'count').map((g) => g.problem.problemId)).toEqual([
      'p-3',
      'p-2',
      'p-1',
    ])
    expect(sortedReviewProblems(items, 'waiting')[0]?.problem.problemId).toBe('p-3')
  })
  it.each([
    [0, '0 работ'],
    [1, '1 работа'],
    [2, '2 работы'],
    [5, '5 работ'],
    [11, '11 работ'],
    [12, '12 работ'],
    [21, '21 работа'],
    [24, '24 работы'],
    [111, '111 работ'],
  ])('declines %s', (count, expected) => {
    expect(workCount(Number(count))).toBe(expected)
  })
  it.each([
    [-1, '0 мин'],
    [59, '59 мин'],
    [60, '1 ч'],
    [61, '1 ч 1 мин'],
    [1440, '1 д'],
    [1501, '1 д 1 ч'],
  ])('formats waiting %s', (minutes, expected) => {
    expect(formatReviewWaiting(Number(minutes))).toBe(expected)
  })
  it('restores all URL settings and tolerates invalid optional settings', () => {
    const search = {
      queueCourse: 'c-1',
      queueGroup: 'g-1',
      queueView: 'works',
      queueSort: 'count',
      queueTableSort: 'student',
    }
    expect(reviewQueueSearchSchema.parse(Object.fromEntries(new URLSearchParams(search)))).toEqual(
      search,
    )
    expect(
      reviewQueueSearchSchema.parse({ queueView: 'bad', queueSort: [], queueCourse: 5 }),
    ).toEqual({ queueView: undefined, queueSort: undefined, queueCourse: undefined })
  })
})

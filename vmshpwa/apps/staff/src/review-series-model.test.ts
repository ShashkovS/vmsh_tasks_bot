import { describe, expect, it, vi } from 'vitest'
import type { ReviewQueueItem } from '@vmsh/contracts'
import { allReviewItems, reviewProblemGroups, seriesCandidates } from './review-series-model'

function item(id: string, problemId: string, day: string): ReviewQueueItem {
  return {
    queueId: id,
    logicalCaseId: problemId,
    student: { studentId: `student-${id}`, displayName: 'Ученик' },
    submittedAt: day,
    lock: null,
    branches: [
      {
        queueId: id,
        problemId,
        problemNumber: '0н.5',
        problemTitle: 'Квадрат',
        courseId: 'c-1',
        courseName: 'ВМШ',
        groupId: 'g-1',
        groupName: 'Начинающие',
        groupShortCode: 'н',
        groupColorKey: null,
        submittedAt: day,
        leaseVersion: 0,
      },
    ],
  }
}
describe('serial review selection', () => {
  it('orders problems by their oldest submission, counts each logical case once', () => {
    const a = item('q-1', 'p-1', '2026-09-07'),
      b = item('q-2', 'p-2', '2026-09-06')
    a.branches.push(a.branches[0]!)
    const groups = reviewProblemGroups([a, b, item('q-3', 'p-1', '2026-09-08')])
    expect(groups.map((g) => [g.problem.problemId, g.items.length])).toEqual([
      ['p-2', 1],
      ['p-1', 2],
    ])
  })
  it('excludes completed, prepared and locked cases while randomizing oldest candidates', () => {
    const items = Array.from({ length: 8 }, (_, i) => item(`q-${i}`, 'p-1', '2026-09-07'))
    items[1]!.lock = {
      kind: 'pwa',
      teacher: { teacherId: 'u-2', displayName: 'Учитель' },
      expiresAt: '2026-09-07',
      isOwnedByCurrentStaff: false,
    }
    const picked = seriesCandidates(items, 'p-1', new Set(['q-0']), () => 0)
    expect(picked.map((i) => i.queueId)).toEqual(['q-3', 'q-4', 'q-5', 'q-6', 'q-2', 'q-7'])
  })
  it('loads all pages, including problems outside the initial queue page', async () => {
    const list = vi
      .fn()
      .mockResolvedValueOnce({ items: [item('q-1', 'p-1', '2026-09-07')], nextCursor: 'q-1' })
      .mockResolvedValueOnce({ items: [item('q-2', 'p-2', '2026-09-07')], nextCursor: null })
    expect(await allReviewItems({ list })).toHaveLength(2)
    expect(list).toHaveBeenLastCalledWith({ cursor: 'q-1' }, {})
  })
  it('counts solutions to the same task across pages without counting synonym branches twice', async () => {
    const first = item('q-1', 'shared-synonym', '2026-09-07')
    first.branches[0]!.problemId = 'p-1'
    first.branches.push({ ...first.branches[0]!, queueId: 'q-1-peer', problemId: 'p-2' })
    const second = item('q-2', 'shared-synonym', '2026-09-08')
    second.branches[0]!.problemId = 'p-1'
    const list = vi
      .fn()
      .mockResolvedValueOnce({ items: [first], nextCursor: 'q-1' })
      .mockResolvedValueOnce({ items: [second], nextCursor: null })
    const groups = reviewProblemGroups(await allReviewItems({ list }))
    expect(groups.map((group) => [group.problem.problemId, group.items.length])).toEqual([
      ['p-1', 2],
      ['p-2', 1],
    ])
    expect(seriesCandidates([first, second], 'p-1', new Set(['q-1']))).toEqual([second])
  })
})

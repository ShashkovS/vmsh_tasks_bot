import { describe, expect, it } from 'vitest'

import {
  createEnrollmentProjection,
  inheritClassroomAssignments,
  materializeScheduleSnapshot,
  projectSynonymSubmissions,
  resolveCourseNotification,
  resolveTelegramBindings,
  scoreGroupSheets,
  selectBestLessonGroup,
  splitSynonymStatuses,
} from './multi-course-projection'

describe('multi-course prototype projections', () => {
  it('allows one active group and several allowed groups within a course', () => {
    expect(
      createEnrollmentProjection({
        courseId: 'math',
        activeGroupId: 'beginner',
        allowedGroupIds: ['beginner', 'continuing', 'beginner'],
      }),
    ).toEqual({
      courseId: 'math',
      activeGroupId: 'beginner',
      allowedGroupIds: ['beginner', 'continuing'],
    })
    expect(() =>
      createEnrollmentProjection({
        courseId: 'math',
        activeGroupId: 'expert',
        allowedGroupIds: ['beginner'],
      }),
    ).toThrow(/active group/)
  })

  it('materializes a group schedule without later template mutation', () => {
    const template = {
      conditionAt: 'Monday 16:30',
      hintAt: 'Saturday 12:00',
      closesAt: 'Sunday 13:00',
      solutionAt: 'Sunday 14:00',
      sourceVersion: 4,
    }
    const snapshot = materializeScheduleSnapshot(template, { conditionAt: 'Tuesday 17:00' })
    template.conditionAt = 'Wednesday 18:00'
    expect(snapshot.conditionAt).toBe('Tuesday 17:00')
    expect(snapshot.sourceVersion).toBe(4)
  })

  it('adds course and group news but lets group material targets replace defaults', () => {
    const resolved = resolveTelegramBindings(
      [
        { id: 'course-news', owner: 'course', purpose: 'news-source' },
        { id: 'course-target', owner: 'course', purpose: 'materials-target' },
      ],
      [
        { id: 'group-news', owner: 'group', purpose: 'news-source' },
        { id: 'group-target', owner: 'group', purpose: 'materials-target' },
      ],
    )
    expect(resolved.map(({ id }) => id)).toEqual(['course-news', 'group-news', 'group-target'])
  })

  it('merges chronology without changing concrete IDs and targets the latest problem', () => {
    const submissions = [
      { id: 'sub-2', problemId: 'problem-b', createdAt: '2026-01-26T10:00:00Z' },
      { id: 'sub-1', problemId: 'problem-a', createdAt: '2026-01-25T20:00:00Z' },
    ]
    const projection = projectSynonymSubmissions(submissions)
    expect(projection.submissionIds).toEqual(['sub-1', 'sub-2'])
    expect(projection.verdictTargetProblemId).toBe('problem-b')
    expect(submissions.map(({ id }) => id)).toEqual(['sub-2', 'sub-1'])
  })

  it('restores each problem status after a synonym split', () => {
    expect(
      splitSynonymStatuses(
        ['problem-a', 'problem-b'],
        [
          {
            id: 'sub-a',
            problemId: 'problem-a',
            createdAt: '2026-01-25T20:00:00Z',
            verdict: 'accepted',
          },
          { id: 'sub-b', problemId: 'problem-b', createdAt: '2026-01-26T10:00:00Z' },
        ],
      ),
    ).toEqual({ 'problem-a': 'accepted', 'problem-b': 'submitted' })
  })

  it('counts a synonym once in each group sheet and selects the best stable group', () => {
    const scores = scoreGroupSheets([
      { groupId: 'beginner', synonymGroupId: 'rook', score: 0.7 },
      { groupId: 'beginner', synonymGroupId: 'rook', score: 1 },
      { groupId: 'beginner', synonymGroupId: 'train', score: 0.5 },
      { groupId: 'continuing', synonymGroupId: 'rook', score: 1 },
      { groupId: 'continuing', synonymGroupId: 'train', score: 0.5 },
    ])
    expect(scores).toEqual({ beginner: 1.5, continuing: 1.5 })
    expect(selectBestLessonGroup(scores, { continuing: 2, beginner: 1 })).toBe('beginner')
  })

  it('keeps course notification overrides independent', () => {
    expect(resolveCourseNotification(true, false)).toBe(false)
    expect(resolveCourseNotification(true, undefined)).toBe(true)
  })

  it('inherits only assignments for groups participating in an in-person event', () => {
    const previous = [
      { studentUserId: '1', groupId: 'math-beginner', classroomId: '201' },
      { studentUserId: '2', groupId: 'physics-intro', classroomId: '401' },
      { studentUserId: '3', groupId: 'math-expert', classroomId: '301' },
    ]
    const inherited = inheritClassroomAssignments(['math-beginner', 'physics-intro'], previous)
    expect(inherited).toEqual(previous.slice(0, 2))
    expect(inherited[0]).not.toBe(previous[0])
  })
})

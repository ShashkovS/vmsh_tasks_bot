import { describe, expect, it } from 'vitest'
import { supportProblemLabel } from './staff-support-pages'

describe('question problem heading', () => {
  const context = {
    courseId: null,
    courseName: null,
    groupId: null,
    groupName: null,
    groupLessonId: null,
    problemId: 'p-1',
    problemTitle: 'Квадрат',
    problemNumber: '0н.4а',
  }
  it('includes lesson, group, problem and subproblem with title', () => {
    expect(supportProblemLabel(context)).toBe('0н.4а · Квадрат')
  })
  it('keeps general questions readable', () => {
    expect(
      supportProblemLabel({ ...context, problemId: null, problemTitle: null, problemNumber: null }),
    ).toBe('Общий вопрос по занятию')
  })
})

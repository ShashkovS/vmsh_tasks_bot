import { describe, expect, it } from 'vitest'

import { staffStatisticsResponseSchema } from './staff-statistics'

const response = {
  schemaVersion: 1,
  courses: [
    {
      courseId: 'course.math',
      code: 'math',
      name: 'Математика',
      subjectCode: 'math',
      status: 'active',
      groups: [
        {
          groupId: 'group.beginner',
          code: 'н',
          name: 'Начинающие',
          colorKey: 'beginner',
          status: 'active',
        },
      ],
    },
  ],
  selectedCourseId: 'course.math',
  selectedGroupId: null,
  run: {
    runId: 'analytics.run-1',
    algorithm: 'a53-compatible',
    algorithmVersion: '1',
    inputThroughResultId: 179,
    completedAt: '2026-08-02T10:01:00Z',
  },
  lessons: [
    {
      lessonNumber: 41,
      studentCount: 2,
      meanSimpleStrength: 7,
      meanComplexStrength: 4,
      meanMaxComplexStrength: 8,
      meanSolvedItems: 3.5,
      completionRate: 70,
      solvedDistribution: [2, 5],
      groups: [
        {
          groupId: 'group.beginner',
          code: 'н',
          name: 'Начинающие',
          colorKey: 'beginner',
          sortOrder: 1,
          studentCount: 2,
        },
      ],
    },
  ],
  requestId: 'request-statistics-1',
} as const

describe('Staff statistics contract', () => {
  it('accepts an anonymous aggregate snapshot', () => {
    expect(staffStatisticsResponseSchema.parse(response).lessons[0]?.studentCount).toBe(2)
  })

  it('rejects an inconsistent distribution or selected group', () => {
    expect(() =>
      staffStatisticsResponseSchema.parse({
        ...response,
        selectedGroupId: 'group.unknown',
        lessons: [{ ...response.lessons[0], solvedDistribution: [2] }],
      }),
    ).toThrow()
  })

  it('requires a completed run for lesson rows', () => {
    expect(() => staffStatisticsResponseSchema.parse({ ...response, run: null })).toThrow()
  })
})

import { describe, expect, it } from 'vitest'

import { staffDashboardResponseSchema } from './staff-dashboard'

const fixture = {
  schemaVersion: 1,
  generatedAt: '2026-08-02T12:00:00Z',
  summary: {
    review: { totalCases: 8, claimedByOthers: 2 },
    questions: { awaitingStaff: 3, olderThanOneHour: 1 },
    publications: { conditionsPublished: 1, groupLessons: 1 },
    oral: { openWindows: 1, upcomingWindows: 0 },
    delivery: null,
  },
  lessons: [
    {
      groupLessonId: 'lesson.math.beginner.41',
      lessonNumber: 41,
      cycleAnchorDate: '2026-08-02',
      course: { courseId: 'course.math', code: 'math', name: 'Математика 5–7' },
      group: {
        groupId: 'group.beginner',
        code: 'н',
        name: 'Начинающие',
        colorKey: 'beginner',
      },
      phase: 'active',
      publications: {
        condition: { state: 'published', scheduledAt: null },
        hint: { state: 'scheduled', scheduledAt: '2026-08-08T12:00:00Z' },
        solution: { state: 'none', scheduledAt: null },
      },
      oral: { openWindows: 1, upcomingWindows: 0 },
    },
  ],
  requestId: 'dashboard-request',
} as const

describe('Staff dashboard contract', () => {
  it('accepts the aggregate teacher projection', () => {
    expect(staffDashboardResponseSchema.parse(fixture).summary.review.totalCases).toBe(8)
  })

  it('rejects row-level Student data and inconsistent counts', () => {
    expect(() => staffDashboardResponseSchema.parse({ ...fixture, studentId: 17 })).toThrow()
    expect(() =>
      staffDashboardResponseSchema.parse({
        ...fixture,
        summary: {
          ...fixture.summary,
          publications: { conditionsPublished: 1, groupLessons: 2 },
        },
      }),
    ).toThrow()
  })
})

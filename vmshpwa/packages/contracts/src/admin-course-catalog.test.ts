import { describe, expect, it } from 'vitest'

import {
  adminCourseCatalogResponseSchema,
  createAdminCourseRequestSchema,
  createAdminGroupLessonRequestSchema,
  saveAdminGroupRequestSchema,
} from './admin-course-catalog'

describe('Staff course catalog contract', () => {
  it('accepts a strict catalog and preserves Cyrillic group codes', () => {
    const parsed = adminCourseCatalogResponseSchema.parse({
      schemaVersion: 1,
      season: {
        seasonId: 'season-2026',
        code: '2026',
        title: '2026–2027',
        status: 'active',
      },
      courses: [
        {
          courseId: 'course-math',
          code: 'math-57',
          name: 'Математика 5–7',
          subjectCode: 'math',
          status: 'active',
          sortOrder: 1,
          accentKey: 'math',
          activeStudents: 1,
          groups: [
            {
              groupId: 'group-beginner',
              shortCode: 'н',
              name: 'Начинающие',
              status: 'active',
              colorKey: 'beginner',
              sortOrder: 1,
              allowSelfSwitch: false,
              isDefault: false,
              isSystem: false,
              scoreWeight: 1,
              activeStudents: 1,
              version: 1,
            },
          ],
          version: 1,
        },
      ],
      requestId: 'request-1',
    })
    expect(parsed.courses[0]?.groups[0]?.shortCode).toBe('н')
  })

  it('normalizes editable codes and rejects unknown fields', () => {
    expect(
      createAdminCourseRequestSchema.parse({
        schemaVersion: 1,
        seasonId: 'season-2026',
        code: ' Physics-7 ',
        name: ' Физика 7 ',
        subjectCode: ' Physics ',
        status: 'draft',
        sortOrder: 2,
        accentKey: 'physics',
      }),
    ).toMatchObject({ code: 'physics-7', name: 'Физика 7', subjectCode: 'physics' })
    expect(() =>
      saveAdminGroupRequestSchema.parse({
        schemaVersion: 1,
        shortCode: 'dp2',
        name: 'Динамика',
        status: 'active',
        colorKey: 'continuing',
        sortOrder: 2,
        allowSelfSwitch: true,
        scoreWeight: 1,
        unexpected: true,
      }),
    ).toThrow()
  })

  it('accepts a real diagnostic lesson numbered zero', () => {
    expect(
      createAdminGroupLessonRequestSchema.parse({
        schemaVersion: 1,
        courseId: 'course-math',
        groupId: 'group-beginner',
        lessonNumber: 0,
        title: 'Нулевое занятие',
        cycleAnchorDate: '2026-09-06',
        businessTimezone: 'Europe/Moscow',
        opensLocalTime: null,
        submissionClosesLocalTime: '2026-09-12T20:50',
        hintScheduledLocalTime: null,
        solutionScheduledLocalTime: null,
      }).lessonNumber,
    ).toBe(0)
  })
})

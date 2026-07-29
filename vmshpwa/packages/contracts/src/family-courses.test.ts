import { describe, expect, it } from 'vitest'

import {
  familyChildCoursesResponseSchema,
  familyChildHomeResponseSchema,
  familyCourseQueryKeys,
} from './family-courses'

const response = {
  student: {
    studentId: 'student.one',
    displayName: 'Анна Петрова',
    grade: 7,
    birthday: '2012-01-07',
    relationshipLabel: 'родитель',
    isPrimary: true,
  },
  enrollments: [
    {
      enrollmentId: 'enrollment.one',
      studentId: 'student.one',
      course: {
        courseId: 'course.math',
        code: 'math',
        name: 'Математика 5–7',
        subjectCode: 'math',
        status: 'active',
        sortOrder: 1,
        accentKey: 'math',
        version: 1,
      },
      activeGroupId: 'group.beginner',
      allowedGroups: [
        {
          groupId: 'group.beginner',
          courseId: 'course.math',
          code: 'н',
          name: 'Начинающие',
          status: 'active',
          sortOrder: 1,
          colorKey: 'beginner',
          version: 1,
        },
      ],
      attendanceMode: 'online',
      status: 'active',
      version: 1,
    },
  ],
}

describe('Family child course contract', () => {
  it('accepts one linked child with course-scoped enrollments', () => {
    expect(familyChildCoursesResponseSchema.parse(response)).toEqual(response)
  })

  it('rejects an enrollment belonging to another child', () => {
    const invalid = structuredClone(response)
    invalid.enrollments[0]!.studentId = 'student.other'
    expect(() => familyChildCoursesResponseSchema.parse(invalid)).toThrow()
  })

  it('keeps query state isolated by Family account and child', () => {
    expect(
      familyCourseQueryKeys.child(
        { audience: 'family', accountId: 'account.family' },
        'student.one',
      ),
    ).not.toEqual(
      familyCourseQueryKeys.child(
        { audience: 'family', accountId: 'account.family' },
        'student.two',
      ),
    )
  })

  it('accepts a current published lesson or an empty course', () => {
    const home = {
      student: response.student,
      courses: [
        {
          enrollment: response.enrollments[0],
          progress: {
            courseId: 'course.math',
            summary: {
              attempted: 1,
              accepted: 1,
              partial: 0,
              needsWork: 0,
              awaitingReview: 0,
            },
            lessons: [],
            activity: [],
            analytics: null,
            achievements: [],
          },
          currentLesson: {
            groupLessonId: 'group-lesson.41',
            courseLessonId: 'course-lesson.41',
            lessonNumber: 41,
            title: 'Занятие 41',
            cycleAnchorDate: '2026-09-14',
            businessTimezone: 'Europe/Moscow',
            problemCount: 12,
          },
        },
      ],
    }
    expect(familyChildHomeResponseSchema.parse(home)).toEqual(home)
    const withoutLesson = {
      ...home,
      courses: [
        {
          enrollment: response.enrollments[0],
          progress: home.courses[0]!.progress,
          currentLesson: null,
        },
      ],
    }
    expect(familyChildHomeResponseSchema.parse(withoutLesson)).toEqual(withoutLesson)
  })
})

import type { ZodType } from 'zod'
import { describe, expect, it } from 'vitest'

import invalidCourseFixture from '../fixtures/courses/invalid.v1.json'
import studentAccessFixture from '../fixtures/courses/student-access.v1.json'
import studentHomeFixture from '../fixtures/courses/student-home.v1.json'
import studentLessonsFixture from '../fixtures/courses/student-lessons.v1.json'
import studentProblemsFixture from '../fixtures/courses/student-problems.v1.json'

import {
  courseContractFixtureSchema,
  courseEnrollmentSchema,
  courseInvalidContractFixtureSchema,
  courseQueryKeys,
  courseSummarySchema,
  groupSummarySchema,
  studentHomeContractFixtureSchema,
  studentHomeResponseSchema,
  studentLessonContractFixtureSchema,
  studentLessonListResponseSchema,
  studentLessonSummarySchema,
  studentProblemContractFixtureSchema,
  studentProblemListResponseSchema,
  studentCourseAccessResponseSchema,
  type CourseInvalidFixtureTarget,
} from './courses'

const invalidTargetSchemas: Record<CourseInvalidFixtureTarget, ZodType> = {
  course: courseSummarySchema,
  group: groupSummarySchema,
  enrollment: courseEnrollmentSchema,
  student_course_access_response: studentCourseAccessResponseSchema,
}

describe('Phase-1 course access contracts', () => {
  it('keeps the synthetic multi-course fixture in parity with the versioned contract', () => {
    expect(courseContractFixtureSchema.parse(studentAccessFixture)).toEqual(studentAccessFixture)
  })

  it('represents one active group and one-or-more allowed groups per course', () => {
    const response = studentCourseAccessResponseSchema.parse(studentAccessFixture.response)
    expect(response.enrollments).toHaveLength(2)

    for (const enrollment of response.enrollments) {
      expect(enrollment.allowedGroups.length).toBeGreaterThan(0)
      expect(enrollment.allowedGroups.map((group) => group.groupId)).toContain(
        enrollment.activeGroupId,
      )
      expect(
        enrollment.allowedGroups.every((group) => group.courseId === enrollment.course.courseId),
      ).toBe(true)
    }
    expect(response.enrollments[0]?.allowedGroups).toHaveLength(2)
    expect(response.enrollments[0]?.attendanceMode).toBe('in_person')
  })

  it('rejects every versioned invalid fixture case', () => {
    const fixture = courseInvalidContractFixtureSchema.parse(invalidCourseFixture)
    for (const invalidCase of fixture.cases) {
      expect(
        invalidTargetSchemas[invalidCase.target].safeParse(invalidCase.payload).success,
        invalidCase.name,
      ).toBe(false)
    }
  })

  it('rejects duplicate allowed groups within an enrollment', () => {
    const enrollment = studentCourseAccessResponseSchema.parse(studentAccessFixture.response)
      .enrollments[0]
    if (!enrollment) throw new Error('Expected a fixture enrollment')

    expect(() =>
      courseEnrollmentSchema.parse({
        ...enrollment,
        allowedGroups: [enrollment.allowedGroups[0], enrollment.allowedGroups[0]],
      }),
    ).toThrow()
  })

  it('keys every course resource by principal, course, and group context', () => {
    const principal = { audience: 'student' as const, accountId: 'account-student-fixture' }
    const otherPrincipal = { audience: 'student' as const, accountId: 'account-student-other' }

    expect(courseQueryKeys.enrollment(principal, 'course-fixture-alpha')).toEqual([
      'principal',
      'student',
      'account-student-fixture',
      'courses',
      'course-fixture-alpha',
      'enrollment',
    ])
    expect(
      courseQueryKeys.group(principal, 'course-fixture-alpha', 'group-fixture-alpha-two'),
    ).toEqual([
      'principal',
      'student',
      'account-student-fixture',
      'courses',
      'course-fixture-alpha',
      'groups',
      'group-fixture-alpha-two',
    ])
    expect(courseQueryKeys.list(principal)).not.toEqual(courseQueryKeys.list(otherPrincipal))
    expect(() => courseQueryKeys.detail(principal, '../unsafe-course')).toThrow()
  })

  it('validates a reverse-ordered lesson page with independent cutoff and solution times', () => {
    const fixture = studentLessonContractFixtureSchema.parse(studentLessonsFixture)
    const current = fixture.response.lessons[0]

    expect(current?.lessonNumber).toBe(42)
    expect(current?.window?.submissionClosesAt).toBe('2026-09-26T17:50:00.000000Z')
    expect(current?.window?.solutionScheduledAt).toBe('2026-09-26T18:00:00.000000Z')
    expect(current?.materials.solution.status).toBe('unavailable')
    expect(fixture.response.lessons.map((lesson) => lesson.lessonNumber)).toEqual([42, 41])
  })

  it('rejects hidden condition projections and inconsistent lesson pages', () => {
    const lesson =
      studentLessonContractFixtureSchema.parse(studentLessonsFixture).response.lessons[0]
    if (!lesson) throw new Error('Expected a fixture lesson')

    expect(
      studentLessonSummarySchema.safeParse({
        ...lesson,
        materials: { ...lesson.materials, condition: { status: 'unavailable' } },
      }).success,
    ).toBe(false)
    expect(
      studentLessonListResponseSchema.safeParse({
        ...studentLessonsFixture.response,
        lessons: [...studentLessonsFixture.response.lessons].reverse(),
      }).success,
    ).toBe(false)
  })

  it('separates lesson pages from exact lesson query keys', () => {
    const principal = { audience: 'student' as const, accountId: 'account-student-fixture' }
    const pageKey = courseQueryKeys.lessons(
      principal,
      'course-fixture-alpha',
      'group-fixture-alpha-one',
    )
    const lessonKey = courseQueryKeys.lesson(
      principal,
      'course-fixture-alpha',
      'group-fixture-alpha-one',
      'group-lesson-fixture-42-alpha-one',
    )
    const archiveKey = courseQueryKeys.lessonArchive(
      principal,
      'course-fixture-alpha',
      'group-fixture-alpha-one',
    )

    expect(pageKey).not.toEqual(lessonKey)
    expect(archiveKey).not.toEqual(pageKey)
    expect(archiveKey).not.toEqual(lessonKey)
    expect(() =>
      courseQueryKeys.lessons(
        principal,
        'course-fixture-alpha',
        'group-fixture-alpha-one',
        '../unsafe-cursor',
      ),
    ).toThrow()
  })

  it('validates a multi-course home with one visible lesson and one empty course', () => {
    const response = studentHomeContractFixtureSchema.parse(studentHomeFixture).response

    expect(response.courses).toHaveLength(2)
    expect(response.courses[0]?.phase).toBe('solving')
    expect(response.courses[0]?.currentLesson?.groupId).toBe('group-fixture-alpha-one')
    expect(response.courses[1]).toMatchObject({ phase: 'no_lesson', currentLesson: null })
  })

  it('validates exact published problems and honest persisted work states', () => {
    const response = studentProblemContractFixtureSchema.parse(studentProblemsFixture).response

    expect(response.problems.map((problem) => problem.status)).toEqual([
      'accepted',
      'checking',
      'needs-work',
    ])
    expect(response.problems[0]?.problemId).toBe('problem-fixture-42-1')
    expect(response.problems[1]?.verdict).toBeNull()
  })

  it('rejects duplicate public identities and verdicts on pending work', () => {
    const response = studentProblemContractFixtureSchema.parse(studentProblemsFixture).response
    const first = response.problems[0]
    const second = response.problems[1]
    if (!first || !second) throw new Error('Expected problem fixtures')

    expect(
      studentProblemListResponseSchema.safeParse({
        ...response,
        problems: [first, { ...second, problemId: first.problemId }],
      }).success,
    ).toBe(false)
    expect(
      studentProblemListResponseSchema.safeParse({
        ...response,
        problems: [{ ...second, verdict: first.verdict }],
      }).success,
    ).toBe(false)
  })

  it('rejects a home lesson from a non-active group and duplicate courses', () => {
    const parsed = studentHomeContractFixtureSchema.parse(studentHomeFixture).response
    const first = parsed.courses[0]
    if (!first || first.currentLesson === null) throw new Error('Expected a current lesson')

    expect(
      studentHomeResponseSchema.safeParse({
        ...parsed,
        courses: [
          {
            ...first,
            currentLesson: {
              ...first.currentLesson,
              groupId: 'group-fixture-alpha-two',
            },
          },
        ],
      }).success,
    ).toBe(false)
    expect(
      studentHomeResponseSchema.safeParse({ ...parsed, courses: [first, first] }).success,
    ).toBe(false)
  })

  it('rejects unknown fixture versions', () => {
    expect(
      courseContractFixtureSchema.safeParse({
        ...studentAccessFixture,
        fixtureVersion: 2,
      }).success,
    ).toBe(false)
    expect(
      courseInvalidContractFixtureSchema.safeParse({
        ...invalidCourseFixture,
        fixtureVersion: 2,
      }).success,
    ).toBe(false)
  })
})

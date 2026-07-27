import type { ZodType } from 'zod'
import { describe, expect, it } from 'vitest'

import invalidCourseFixture from '../fixtures/courses/invalid.v1.json'
import studentAccessFixture from '../fixtures/courses/student-access.v1.json'

import {
  courseContractFixtureSchema,
  courseEnrollmentSchema,
  courseInvalidContractFixtureSchema,
  courseQueryKeys,
  courseSummarySchema,
  groupSummarySchema,
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

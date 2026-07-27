import { z } from 'zod'

import {
  canonicalTokenSchema,
  principalQueryKey,
  publicIdSchema,
  type PrincipalQueryScope,
} from './auth'

/**
 * Phase-1 course enrollment/access contracts. The server remains authoritative
 * for every scope; URL state is only resource context. See
 * `docs/courses-groups-and-lessons.md` and `src/courses.test.ts`.
 */

const displayTextSchema = z.string().trim().min(1).max(200)
const shortCodeSchema = z.string().trim().min(1).max(64)
const versionSchema = z.number().int().positive()
export const courseStatusSchema = z.enum(['draft', 'active', 'archived'])
export type CourseStatus = z.infer<typeof courseStatusSchema>

export const groupStatusSchema = z.enum(['draft', 'active', 'archived'])
export type GroupStatus = z.infer<typeof groupStatusSchema>

export const enrollmentStatusSchema = z.enum(['active', 'paused', 'archived'])
export type EnrollmentStatus = z.infer<typeof enrollmentStatusSchema>

export const courseSummarySchema = z
  .object({
    courseId: publicIdSchema,
    code: shortCodeSchema,
    name: displayTextSchema,
    subjectCode: shortCodeSchema,
    status: courseStatusSchema,
    sortOrder: z.number().int().nonnegative(),
    accentKey: canonicalTokenSchema,
    version: versionSchema,
  })
  .strip()
export type CourseSummary = z.infer<typeof courseSummarySchema>

export const groupSummarySchema = z
  .object({
    groupId: publicIdSchema,
    courseId: publicIdSchema,
    code: shortCodeSchema,
    name: displayTextSchema,
    status: groupStatusSchema,
    sortOrder: z.number().int().nonnegative(),
    colorKey: canonicalTokenSchema,
    version: versionSchema,
  })
  .strip()
export type GroupSummary = z.infer<typeof groupSummarySchema>

export const attendanceModeSchema = z.enum(['online', 'in_person'])
export type AttendanceMode = z.infer<typeof attendanceModeSchema>

export const courseEnrollmentSchema = z
  .object({
    enrollmentId: publicIdSchema,
    studentId: publicIdSchema,
    course: courseSummarySchema,
    activeGroupId: publicIdSchema,
    allowedGroups: z.array(groupSummarySchema).min(1),
    attendanceMode: attendanceModeSchema,
    status: enrollmentStatusSchema,
    version: versionSchema,
  })
  .strip()
  .superRefine((enrollment, context) => {
    const seenGroupIds = new Set<string>()
    enrollment.allowedGroups.forEach((group, index) => {
      if (group.courseId !== enrollment.course.courseId) {
        context.addIssue({
          code: 'custom',
          message: 'Allowed group must belong to the enrollment course',
          path: ['allowedGroups', index, 'courseId'],
        })
      }
      if (seenGroupIds.has(group.groupId)) {
        context.addIssue({
          code: 'custom',
          message: 'Allowed group IDs must be unique within an enrollment',
          path: ['allowedGroups', index, 'groupId'],
        })
      }
      seenGroupIds.add(group.groupId)
    })

    if (!seenGroupIds.has(enrollment.activeGroupId)) {
      context.addIssue({
        code: 'custom',
        message: 'Active group must be one of the allowed groups',
        path: ['activeGroupId'],
      })
    }
  })
export type CourseEnrollment = z.infer<typeof courseEnrollmentSchema>

export const studentCourseAccessResponseSchema = z
  .object({
    studentId: publicIdSchema,
    enrollments: z.array(courseEnrollmentSchema),
  })
  .strip()
  .superRefine((response, context) => {
    const seenEnrollmentIds = new Set<string>()
    const seenCourseIds = new Set<string>()
    response.enrollments.forEach((enrollment, index) => {
      if (enrollment.studentId !== response.studentId) {
        context.addIssue({
          code: 'custom',
          message: 'Enrollment student must match response student',
          path: ['enrollments', index, 'studentId'],
        })
      }
      if (seenEnrollmentIds.has(enrollment.enrollmentId)) {
        context.addIssue({
          code: 'custom',
          message: 'Enrollment IDs must be unique',
          path: ['enrollments', index, 'enrollmentId'],
        })
      }
      if (seenCourseIds.has(enrollment.course.courseId)) {
        context.addIssue({
          code: 'custom',
          message: 'A student may have only one enrollment per course',
          path: ['enrollments', index, 'course', 'courseId'],
        })
      }
      seenEnrollmentIds.add(enrollment.enrollmentId)
      seenCourseIds.add(enrollment.course.courseId)
    })
  })
export type StudentCourseAccessResponse = z.infer<typeof studentCourseAccessResponseSchema>

export const courseQueryKeys = {
  all: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'courses'] as const,
  list: (principal: PrincipalQueryScope) => [...courseQueryKeys.all(principal), 'list'] as const,
  detail: (principal: PrincipalQueryScope, courseId: string) =>
    [...courseQueryKeys.all(principal), publicIdSchema.parse(courseId)] as const,
  enrollment: (principal: PrincipalQueryScope, courseId: string) =>
    [...courseQueryKeys.detail(principal, courseId), 'enrollment'] as const,
  group: (principal: PrincipalQueryScope, courseId: string, groupId: string) =>
    [
      ...courseQueryKeys.detail(principal, courseId),
      'groups',
      publicIdSchema.parse(groupId),
    ] as const,
} as const

export const COURSE_CONTRACT_FIXTURE_VERSION = 1 as const
const courseContractFixtureVersionSchema = z.literal(COURSE_CONTRACT_FIXTURE_VERSION)

export const courseContractFixtureSchema = z
  .object({
    fixtureVersion: courseContractFixtureVersionSchema,
    response: studentCourseAccessResponseSchema,
  })
  .strict()
export type CourseContractFixture = z.infer<typeof courseContractFixtureSchema>

export const courseInvalidFixtureTargetSchema = z.enum([
  'course',
  'group',
  'enrollment',
  'student_course_access_response',
])
export type CourseInvalidFixtureTarget = z.infer<typeof courseInvalidFixtureTargetSchema>

export const courseInvalidContractFixtureSchema = z
  .object({
    fixtureVersion: courseContractFixtureVersionSchema,
    cases: z
      .array(
        z
          .object({
            name: canonicalTokenSchema,
            target: courseInvalidFixtureTargetSchema,
            payload: z.unknown(),
          })
          .strict(),
      )
      .min(1),
  })
  .strict()
export type CourseInvalidContractFixture = z.infer<typeof courseInvalidContractFixtureSchema>

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

export const lessonCursorSchema = z
  .string()
  .regex(/^(?:0|[1-9][0-9]{0,8})$/, 'Lesson cursor must be a non-negative lesson number')
export type LessonCursor = z.infer<typeof lessonCursorSchema>

export const studentLessonMaterialSchema = z.discriminatedUnion('status', [
  z.object({ status: z.literal('unavailable') }).strip(),
  z
    .object({
      status: z.literal('published'),
      revisionId: publicIdSchema,
      publishedAt: z.iso.datetime(),
      publicationVersion: versionSchema,
    })
    .strip(),
])
export type StudentLessonMaterial = z.infer<typeof studentLessonMaterialSchema>

export const studentLessonWindowSchema = z
  .object({
    windowId: publicIdSchema,
    opensAt: z.iso.datetime().nullable(),
    submissionClosesAt: z.iso.datetime(),
    hintScheduledAt: z.iso.datetime().nullable(),
    solutionScheduledAt: z.iso.datetime().nullable(),
    timezone: z.string().trim().min(1).max(100),
    source: z.enum(['native', 'legacy_schedule', 'manual_backfill']),
    version: versionSchema,
  })
  .strip()
  .superRefine((window, context) => {
    if (window.opensAt !== null && window.opensAt >= window.submissionClosesAt) {
      context.addIssue({
        code: 'custom',
        message: 'Lesson opening must precede the submission cutoff',
        path: ['opensAt'],
      })
    }
  })
export type StudentLessonWindow = z.infer<typeof studentLessonWindowSchema>

export const studentLessonSummarySchema = z
  .object({
    groupLessonId: publicIdSchema,
    courseLessonId: publicIdSchema,
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    lessonNumber: z.number().int().nonnegative(),
    title: displayTextSchema.nullable(),
    cycleAnchorDate: z.iso.date(),
    businessTimezone: z.string().trim().min(1).max(100),
    version: versionSchema,
    problemCount: z.number().int().nonnegative(),
    window: studentLessonWindowSchema.nullable(),
    materials: z
      .object({
        condition: studentLessonMaterialSchema,
        hint: studentLessonMaterialSchema,
        solution: studentLessonMaterialSchema,
      })
      .strip(),
  })
  .strip()
  .superRefine((lesson, context) => {
    if (lesson.materials.condition.status !== 'published') {
      context.addIssue({
        code: 'custom',
        message: 'A Student-visible lesson must have a published condition',
        path: ['materials', 'condition'],
      })
    }
    if (lesson.window !== null && lesson.window.timezone !== lesson.businessTimezone) {
      context.addIssue({
        code: 'custom',
        message: 'Lesson window timezone must match the group lesson timezone',
        path: ['window', 'timezone'],
      })
    }
  })
export type StudentLessonSummary = z.infer<typeof studentLessonSummarySchema>

export const studentProblemTypeSchema = z.enum(['test', 'written', 'oral'])
export type StudentProblemType = z.infer<typeof studentProblemTypeSchema>

export const studentProblemStatusSchema = z.enum([
  'not-started',
  'sent',
  'checking',
  'accepted',
  'needs-work',
  'rejected',
])
export type StudentProblemStatus = z.infer<typeof studentProblemStatusSchema>

export const studentProblemMaterialStatusSchema = z.enum(['unavailable', 'available', 'revealed'])
export type StudentProblemMaterialStatus = z.infer<typeof studentProblemMaterialStatusSchema>

const studentProblemMaterialSchema = z
  .object({ status: studentProblemMaterialStatusSchema })
  .strip()

export const legacyVerdictIdSchema = z.union([
  z.literal(-32768),
  z.literal(-2),
  z.literal(-1),
  z.literal(11),
  z.literal(12),
  z.literal(13),
  z.literal(14),
  z.literal(15),
  z.literal(16),
  z.literal(17),
  z.literal(18),
])
export type LegacyVerdictId = z.infer<typeof legacyVerdictIdSchema>

export const studentProblemVerdictSchema = z
  .object({
    verdictId: legacyVerdictIdSchema,
    symbol: z.string().max(16),
    weight: z.number().min(0).max(1),
  })
  .strip()
export type StudentProblemVerdict = z.infer<typeof studentProblemVerdictSchema>

export const studentProblemSummarySchema = z
  .object({
    problemId: publicIdSchema,
    configVersion: z.number().int().positive(),
    sourceOrdinal: z.number().int().positive(),
    displayNumber: z.string().trim().min(1).max(80),
    hasAnswer: z.boolean().optional(),
    title: z.string().trim().min(1).max(500),
    type: studentProblemTypeSchema,
    answerType: z.number().int().positive().max(99).nullable(),
    materials: z
      .object({
        hint: studentProblemMaterialSchema,
        solution: studentProblemMaterialSchema,
      })
      .strip(),
    status: studentProblemStatusSchema,
    verdict: studentProblemVerdictSchema.nullable(),
  })
  .strip()
  .superRefine((problem, context) => {
    const terminal = ['accepted', 'needs-work', 'rejected'].includes(problem.status)
    if (terminal !== (problem.verdict !== null)) {
      context.addIssue({
        code: 'custom',
        message: 'Only a completed problem status may expose a verdict',
        path: ['verdict'],
      })
    }
    if (problem.status === 'accepted' && problem.verdict !== null && problem.verdict.weight < 0.8) {
      context.addIssue({
        code: 'custom',
        message: 'Accepted problem verdict must meet the solved threshold',
        path: ['verdict', 'weight'],
      })
    }
    if (
      ['needs-work', 'rejected'].includes(problem.status) &&
      problem.verdict !== null &&
      problem.verdict.weight >= 0.8
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Unaccepted problem verdict must stay below the solved threshold',
        path: ['verdict', 'weight'],
      })
    }
  })
export type StudentProblemSummary = z.infer<typeof studentProblemSummarySchema>

export const studentProblemListResponseSchema = z
  .object({
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    groupLessonId: publicIdSchema,
    conditionRevisionId: publicIdSchema,
    problems: z.array(studentProblemSummarySchema).max(2_000),
  })
  .strip()
  .superRefine((response, context) => {
    const seen = new Set<string>()
    response.problems.forEach((problem, index) => {
      if (seen.has(problem.problemId)) {
        context.addIssue({
          code: 'custom',
          message: 'Problem public IDs must be unique in a published list',
          path: ['problems', index, 'problemId'],
        })
      }
      seen.add(problem.problemId)
    })
  })
export type StudentProblemListResponse = z.infer<typeof studentProblemListResponseSchema>

export const studentLessonListResponseSchema = z
  .object({
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    activeGroupId: publicIdSchema,
    lessons: z.array(studentLessonSummarySchema),
    nextCursor: lessonCursorSchema.nullable(),
  })
  .strip()
  .superRefine((response, context) => {
    const groupLessonIds = new Set<string>()
    let previousLessonNumber: number | null = null
    response.lessons.forEach((lesson, index) => {
      if (lesson.courseId !== response.courseId || lesson.groupId !== response.groupId) {
        context.addIssue({
          code: 'custom',
          message: 'Every lesson must belong to the response course and group',
          path: ['lessons', index],
        })
      }
      if (groupLessonIds.has(lesson.groupLessonId)) {
        context.addIssue({
          code: 'custom',
          message: 'Group lesson IDs must be unique',
          path: ['lessons', index, 'groupLessonId'],
        })
      }
      if (previousLessonNumber !== null && lesson.lessonNumber >= previousLessonNumber) {
        context.addIssue({
          code: 'custom',
          message: 'Lessons must use stable reverse lesson-number order',
          path: ['lessons', index, 'lessonNumber'],
        })
      }
      groupLessonIds.add(lesson.groupLessonId)
      previousLessonNumber = lesson.lessonNumber
    })
  })
export type StudentLessonListResponse = z.infer<typeof studentLessonListResponseSchema>

export const studentLessonPhaseSchema = z.enum([
  'no_lesson',
  'published',
  'solving',
  'hints',
  'checking',
  'solutions',
])
export type StudentLessonPhase = z.infer<typeof studentLessonPhaseSchema>

const studentHomeCourseShape = {
  enrollment: courseEnrollmentSchema,
}
export const studentHomeCourseSchema = z
  .discriminatedUnion('phase', [
    z
      .object({
        ...studentHomeCourseShape,
        phase: z.literal('no_lesson'),
        currentLesson: z.null(),
      })
      .strip(),
    z
      .object({
        ...studentHomeCourseShape,
        phase: z.enum(['published', 'solving', 'hints', 'checking', 'solutions']),
        currentLesson: studentLessonSummarySchema,
      })
      .strip(),
  ])
  .superRefine((course, context) => {
    if (
      course.currentLesson !== null &&
      (course.currentLesson.courseId !== course.enrollment.course.courseId ||
        course.currentLesson.groupId !== course.enrollment.activeGroupId)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Current lesson must belong to the enrollment active group',
        path: ['currentLesson'],
      })
    }
  })
export type StudentHomeCourse = z.infer<typeof studentHomeCourseSchema>

export const studentHomeResponseSchema = z
  .object({
    studentId: publicIdSchema,
    generatedAt: z.iso.datetime(),
    courses: z.array(studentHomeCourseSchema),
  })
  .strip()
  .superRefine((response, context) => {
    const courseIds = new Set<string>()
    response.courses.forEach((course, index) => {
      if (course.enrollment.studentId !== response.studentId) {
        context.addIssue({
          code: 'custom',
          message: 'Home enrollment student must match the response student',
          path: ['courses', index, 'enrollment', 'studentId'],
        })
      }
      const courseId = course.enrollment.course.courseId
      if (courseIds.has(courseId)) {
        context.addIssue({
          code: 'custom',
          message: 'Home courses must be unique',
          path: ['courses', index, 'enrollment', 'course', 'courseId'],
        })
      }
      courseIds.add(courseId)
    })
  })
export type StudentHomeResponse = z.infer<typeof studentHomeResponseSchema>

export const courseQueryKeys = {
  all: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'courses'] as const,
  home: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'home'] as const,
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
  lessons: (
    principal: PrincipalQueryScope,
    courseId: string,
    groupId: string,
    cursor: string | null = null,
  ) =>
    [
      ...courseQueryKeys.group(principal, courseId, groupId),
      'lessons',
      'pages',
      cursor === null ? 'first' : lessonCursorSchema.parse(cursor),
    ] as const,
  lessonArchive: (principal: PrincipalQueryScope, courseId: string, groupId: string) =>
    [...courseQueryKeys.group(principal, courseId, groupId), 'lessons', 'archive'] as const,
  lesson: (
    principal: PrincipalQueryScope,
    courseId: string,
    groupId: string,
    groupLessonId: string,
  ) =>
    [
      ...courseQueryKeys.group(principal, courseId, groupId),
      'lessons',
      publicIdSchema.parse(groupLessonId),
    ] as const,
  problems: (
    principal: PrincipalQueryScope,
    courseId: string,
    groupId: string,
    groupLessonId: string,
  ) =>
    [...courseQueryKeys.lesson(principal, courseId, groupId, groupLessonId), 'problems'] as const,
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

export const studentLessonContractFixtureSchema = z
  .object({
    fixtureVersion: courseContractFixtureVersionSchema,
    response: studentLessonListResponseSchema,
  })
  .strict()
export type StudentLessonContractFixture = z.infer<typeof studentLessonContractFixtureSchema>

export const studentHomeContractFixtureSchema = z
  .object({
    fixtureVersion: courseContractFixtureVersionSchema,
    response: studentHomeResponseSchema,
  })
  .strict()
export type StudentHomeContractFixture = z.infer<typeof studentHomeContractFixtureSchema>

export const studentProblemContractFixtureSchema = z
  .object({
    fixtureVersion: courseContractFixtureVersionSchema,
    response: studentProblemListResponseSchema,
  })
  .strict()
export type StudentProblemContractFixture = z.infer<typeof studentProblemContractFixtureSchema>

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

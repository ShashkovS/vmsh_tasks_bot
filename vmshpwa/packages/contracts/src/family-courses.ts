import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { courseEnrollmentSchema } from './courses'

/** Phase-9 read model for one child already linked to the Family account. */
export const familyChildSummarySchema = z
  .object({
    studentId: publicIdSchema,
    displayName: z.string().trim().min(1).max(200),
    grade: z.number().int().min(1).max(11).nullable(),
    birthday: z.iso.date().nullable(),
    relationshipLabel: z.string().trim().min(1).max(80).nullable(),
    isPrimary: z.boolean(),
  })
  .strip()
export type FamilyChildSummary = z.infer<typeof familyChildSummarySchema>

export const familyChildCoursesResponseSchema = z
  .object({
    student: familyChildSummarySchema,
    enrollments: z.array(courseEnrollmentSchema),
  })
  .strip()
  .superRefine((response, context) => {
    const courseIds = new Set<string>()
    response.enrollments.forEach((enrollment, index) => {
      if (enrollment.studentId !== response.student.studentId) {
        context.addIssue({
          code: 'custom',
          message: 'Enrollment must belong to the selected child',
          path: ['enrollments', index, 'studentId'],
        })
      }
      if (courseIds.has(enrollment.course.courseId)) {
        context.addIssue({
          code: 'custom',
          message: 'A child may have only one enrollment per course',
          path: ['enrollments', index, 'course', 'courseId'],
        })
      }
      courseIds.add(enrollment.course.courseId)
    })
  })
export type FamilyChildCoursesResponse = z.infer<typeof familyChildCoursesResponseSchema>

export const familyCourseQueryKeys = {
  child: (principal: PrincipalQueryScope, studentId: string) =>
    [
      ...principalQueryKey(principal),
      'family-child-courses',
      publicIdSchema.parse(studentId),
    ] as const,
}

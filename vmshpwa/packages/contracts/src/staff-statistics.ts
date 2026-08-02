import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const statisticsGroupSchema = z
  .object({
    groupId: publicIdSchema,
    code: z.string().trim().min(1).max(16),
    name: z.string().trim().min(1).max(160),
    colorKey: z.string().trim().min(1).max(32),
    status: z.enum(['active', 'archived']),
  })
  .strip()

const statisticsCourseSchema = z
  .object({
    courseId: publicIdSchema,
    code: z.string().trim().min(1).max(32),
    name: z.string().trim().min(1).max(160),
    subjectCode: z.string().trim().min(1).max(32),
    status: z.enum(['active', 'archived']),
    groups: z.array(statisticsGroupSchema).max(100),
  })
  .strip()

const statisticsRunSchema = z
  .object({
    runId: publicIdSchema,
    algorithm: z.string().trim().min(1).max(64),
    algorithmVersion: z.string().trim().min(1).max(64),
    inputThroughResultId: z.number().int().nonnegative(),
    completedAt: z.iso.datetime({ offset: true }),
  })
  .strip()

const lessonGroupSchema = z
  .object({
    groupId: publicIdSchema,
    code: z.string().trim().min(1).max(16),
    name: z.string().trim().min(1).max(160),
    colorKey: z.string().trim().min(1).max(32),
    sortOrder: z.number().int(),
    studentCount: z.number().int().nonnegative(),
  })
  .strip()

export const staffStatisticsLessonSchema = z
  .object({
    lessonNumber: z.number().int().positive(),
    studentCount: z.number().int().positive(),
    meanSimpleStrength: z.number().min(0).max(10).nullable(),
    meanComplexStrength: z.number().min(0).max(10).nullable(),
    meanMaxComplexStrength: z.number().min(0).max(10).nullable(),
    meanSolvedItems: z.number().nonnegative().nullable(),
    completionRate: z.number().min(0).max(100).nullable(),
    solvedDistribution: z.array(z.number().int().nonnegative()).min(1).max(5000),
    groups: z.array(lessonGroupSchema).min(1).max(100),
  })
  .strip()
  .superRefine((lesson, context) => {
    if (lesson.solvedDistribution.length !== lesson.studentCount) {
      context.addIssue({
        code: 'custom',
        message: 'Distribution size must match the lesson student count',
        path: ['solvedDistribution'],
      })
    }
    if (lesson.groups.reduce((sum, group) => sum + group.studentCount, 0) !== lesson.studentCount) {
      context.addIssue({
        code: 'custom',
        message: 'Group counts must match the lesson student count',
        path: ['groups'],
      })
    }
  })

export const staffStatisticsResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    courses: z.array(statisticsCourseSchema).max(100),
    selectedCourseId: publicIdSchema.nullable(),
    selectedGroupId: publicIdSchema.nullable(),
    run: statisticsRunSchema.nullable(),
    lessons: z.array(staffStatisticsLessonSchema).max(200),
    requestId: z.string().trim().min(1).max(128),
  })
  .strip()
  .superRefine((response, context) => {
    const selectedCourse = response.courses.find(
      (course) => course.courseId === response.selectedCourseId,
    )
    if (response.selectedCourseId !== null && selectedCourse === undefined) {
      context.addIssue({
        code: 'custom',
        message: 'Selected course is absent',
        path: ['selectedCourseId'],
      })
    }
    if (
      response.selectedGroupId !== null &&
      selectedCourse?.groups.some((group) => group.groupId === response.selectedGroupId) !== true
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Selected group is absent',
        path: ['selectedGroupId'],
      })
    }
    if (response.run === null && response.lessons.length > 0) {
      context.addIssue({
        code: 'custom',
        message: 'Lessons require a completed run',
        path: ['lessons'],
      })
    }
    const lessons = new Set<number>()
    response.lessons.forEach((lesson, index) => {
      if (lessons.has(lesson.lessonNumber)) {
        context.addIssue({
          code: 'custom',
          message: 'Lesson numbers must be unique',
          path: ['lessons', index, 'lessonNumber'],
        })
      }
      lessons.add(lesson.lessonNumber)
    })
  })

export type StaffStatisticsResponse = z.infer<typeof staffStatisticsResponseSchema>
export type StaffStatisticsLesson = z.infer<typeof staffStatisticsLessonSchema>

export const staffStatisticsQueryKey = (
  principal: PrincipalQueryScope,
  courseId: string | null,
  groupId: string | null,
) => [...principalQueryKey(principal), 'staff-statistics', courseId, groupId] as const

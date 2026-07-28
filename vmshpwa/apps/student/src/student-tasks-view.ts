import { z } from 'zod'

import {
  publicIdSchema,
  type CourseEnrollment,
  type StudentCourseAccessResponse,
  type StudentLessonSummary,
} from '@vmsh/contracts'

/** Shareable Student Tasks context; URL state never grants server access. */
export const studentTasksSearchSchema = z.object({
  course: publicIdSchema.optional(),
  group: publicIdSchema.optional(),
  lesson: z.coerce.number().int().positive().optional(),
  view: z.enum(['list', 'sheet']).optional().catch(undefined),
  topic: z.string().trim().min(1).max(100).optional(),
})
export type StudentTasksSearch = z.infer<typeof studentTasksSearchSchema>

export type StudentTasksContext =
  | { kind: 'empty' }
  | { kind: 'forbidden'; resource: 'course' | 'group' }
  | { kind: 'ready'; enrollment: CourseEnrollment; groupId: string }

export function resolveStudentTasksContext(
  access: StudentCourseAccessResponse,
  search: StudentTasksSearch,
): StudentTasksContext {
  if (access.enrollments.length === 0) return { kind: 'empty' }
  const enrollment = search.course
    ? access.enrollments.find((candidate) => candidate.course.courseId === search.course)
    : access.enrollments[0]
  if (!enrollment) return { kind: 'forbidden', resource: 'course' }

  const groupId = search.group ?? enrollment.activeGroupId
  if (!enrollment.allowedGroups.some((group) => group.groupId === groupId)) {
    return { kind: 'forbidden', resource: 'group' }
  }
  return { kind: 'ready', enrollment, groupId }
}

export function lessonHeading(lesson: StudentLessonSummary): string {
  return lesson.title?.trim() || `Занятие ${lesson.lessonNumber}`
}

export function publishedMaterialLabel(lesson: StudentLessonSummary): string {
  const available: string[] = []
  if (lesson.materials.hint.status === 'published') available.push('подсказка')
  if (lesson.materials.solution.status === 'published') available.push('решение')
  return available.length === 0 ? 'Только условие' : `Есть ${available.join(' и ')}`
}

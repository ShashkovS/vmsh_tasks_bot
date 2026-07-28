import { z } from 'zod'

import {
  publicIdSchema,
  type CourseEnrollment,
  type StudentCourseAccessResponse,
  type StudentLessonSummary,
  type StudentProblemStatus,
  type StudentProblemSummary,
} from '@vmsh/contracts'
import {
  findVerdict,
  fullVerdictScale,
  type TaskListItemView,
  type TaskStatusView,
  type VerdictView,
} from '@vmsh/product'

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

const taskStatusByValue: Record<StudentProblemStatus, TaskStatusView> = {
  'not-started': { kind: 'not-started', label: 'Не начата', tone: 'neutral' },
  sent: { kind: 'sent', label: 'Отправлено', tone: 'info' },
  checking: { kind: 'checking', label: 'На проверке', tone: 'info' },
  accepted: { kind: 'accepted', label: 'Зачтено', tone: 'success' },
  'needs-work': { kind: 'needs-work', label: 'Нужна доработка', tone: 'warning' },
  rejected: { kind: 'rejected', label: 'Ответ не принят', tone: 'danger' },
}

const verdictKeyByLegacyId = {
  [-32768]: 'no-answer',
  [-2]: 'rejected',
  [-1]: 'rejected',
  [11]: 'rejected',
  [12]: 'minus-dot',
  [13]: 'minus-plus',
  [14]: 'half',
  [15]: 'plus-minus',
  [16]: 'plus-dot',
  [17]: 'plus',
  [18]: 'plus',
} as const

function problemVerdict(problem: StudentProblemSummary): VerdictView | null {
  if (!problem.verdict) return null
  const value = verdictKeyByLegacyId[problem.verdict.verdictId]
  if (value === 'no-answer') {
    return {
      value,
      symbol: problem.verdict.symbol,
      label: 'Нет ответа',
      weight: problem.verdict.weight,
      tone: 'none',
    }
  }
  const canonical = findVerdict(fullVerdictScale, value)
  if (!canonical) return null
  return {
    ...canonical,
    symbol: problem.verdict.symbol,
    weight: problem.verdict.weight,
  }
}

/** Map the server-owned work projection into the accepted Product task row. */
export function toStudentTaskView(
  problem: StudentProblemSummary,
  lessonNumber: number,
  groupCode: string,
): TaskListItemView {
  const verdict = problemVerdict(problem)
  return {
    id: problem.problemId,
    number: `${lessonNumber}${groupCode}.${problem.displayNumber}`,
    title: problem.title,
    type: problem.type,
    status: taskStatusByValue[problem.status],
    ...(verdict === null ? {} : { verdict }),
  }
}

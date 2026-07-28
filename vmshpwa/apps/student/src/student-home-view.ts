import type { CourseEnrollment, StudentHomeCourse } from '@vmsh/contracts'
import type { CourseEnrollmentView } from '@vmsh/product'

type AccentIndex = 0 | 1 | 2 | 3 | 4

function presentationIndex(token: string, fallback: number): AccentIndex {
  const suffix = /(?:^|[_-])([0-4])$/.exec(token)?.[1]
  if (suffix !== undefined) return Number(suffix) as AccentIndex
  return (((Math.max(1, fallback) - 1) % 4) + 1) as AccentIndex
}

export function toCourseEnrollmentView(enrollment: CourseEnrollment): CourseEnrollmentView {
  return {
    course: {
      id: enrollment.course.courseId,
      code: enrollment.course.code,
      name: enrollment.course.name,
      subjectCode: enrollment.course.subjectCode,
      accentIndex: presentationIndex(enrollment.course.accentKey, enrollment.course.sortOrder),
    },
    activeGroupId: enrollment.activeGroupId,
    allowedGroups: enrollment.allowedGroups.map((group) => ({
      id: group.groupId,
      courseId: group.courseId,
      code: group.code,
      name: group.name,
      colorIndex: presentationIndex(group.colorKey, group.sortOrder),
    })),
    attendanceMode: enrollment.attendanceMode === 'in_person' ? 'in-person' : 'online',
  }
}

export function formatCalendarDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${value}T12:00:00Z`))
}

function formatDeadline(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: timezone,
  }).format(new Date(value))
}

export function studentPhaseLabel(course: StudentHomeCourse): string {
  if (course.phase === 'no_lesson') return 'Новое занятие пока не опубликовано'
  const deadline = course.currentLesson.window
    ? formatDeadline(
        course.currentLesson.window.submissionClosesAt,
        course.currentLesson.businessTimezone,
      )
    : null
  switch (course.phase) {
    case 'published':
      return 'Условие опубликовано · время сдачи уточняется'
    case 'solving':
      return deadline ? `Решаем задачи · до ${deadline}` : 'Решаем задачи'
    case 'hints':
      return deadline ? `Подсказки опубликованы · до ${deadline}` : 'Подсказки опубликованы'
    case 'checking':
      return 'Приём завершён · идёт проверка'
    case 'solutions':
      return 'Решения опубликованы'
  }
}

export function problemCountLabel(count: number): string {
  const modulo100 = count % 100
  const modulo10 = count % 10
  const noun =
    modulo100 >= 11 && modulo100 <= 14
      ? 'задач'
      : modulo10 === 1
        ? 'задача'
        : modulo10 >= 2 && modulo10 <= 4
          ? 'задачи'
          : 'задач'
  return `${count} ${noun} в листке`
}

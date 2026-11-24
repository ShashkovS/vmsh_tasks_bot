import { type CourseEnrollment } from '@vmsh/contracts'

type HomeCourse = { enrollment: Pick<CourseEnrollment, 'course' | 'allowedGroups'> }

/** Home dependencies follow its authorized enrollments; scoped-reads-20261013.md. */
export function homeRealtimeResources(courses: readonly HomeCourse[] | undefined): string[] {
  return [
    'home',
    'courses',
    'course-enrollments',
    'live-results',
    ...(courses === undefined
      ? ['courses/*/groups/*/lessons', 'courses/*/work']
      : courses.flatMap(({ enrollment }) => [
          `courses/${enrollment.course.courseId}/work`,
          `courses/${enrollment.course.courseId}/lessons`,
          ...enrollment.allowedGroups.map(
            (group) => `courses/${enrollment.course.courseId}/groups/${group.groupId}/lessons`,
          ),
        ])),
  ]
}

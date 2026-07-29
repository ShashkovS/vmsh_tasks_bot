import { useMemo } from 'react'

import {
  CourseNetworkError,
  PageLayout,
  PageSection,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentCourseProgressQuery,
  useStudentCoursesQuery,
} from '@vmsh/app-shell'
import { ApiResponseError } from '@vmsh/contracts'
import { CourseContext, StrengthTrend, StudentProgress } from '@vmsh/product'
import { Card, CardContent } from '@vmsh/ui'

import { toCourseEnrollmentView } from './student-home-view'

export interface StudentProgressPageProps {
  courseId?: string
  onCourseChange: (courseId: string) => void
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${value}T12:00:00Z`))
}

/** Production personal progress; cohort comparisons are deliberately absent. */
export function StudentProgressPage({ courseId, onCourseChange }: StudentProgressPageProps) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Progress requires a Student principal')
  const client = useMemo(
    () =>
      createStudentCourseClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const scope = { audience: 'student' as const, accountId: principal.accountId }
  const courses = useStudentCoursesQuery(client, scope)
  const enrollment =
    courses.data?.enrollments.find((candidate) => candidate.course.courseId === courseId) ??
    courses.data?.enrollments[0]
  const activeCourseId = enrollment?.course.courseId ?? 'missing'
  const progress = useStudentCourseProgressQuery(
    client,
    scope,
    activeCourseId,
    enrollment !== undefined,
  )

  if (courses.isPending) {
    return (
      <PageLayout title="Прогресс">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (courses.error) {
    return (
      <PageLayout title="Прогресс">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void courses.refetch()}
          state={courses.error instanceof CourseNetworkError ? 'offline' : 'error'}
        />
      </PageLayout>
    )
  }
  if (!enrollment) {
    return (
      <PageLayout title="Прогресс">
        <PageStatePanel state="empty" title="Нет активных курсов" />
      </PageLayout>
    )
  }
  if (progress.isPending) {
    return (
      <PageLayout title="Прогресс">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (progress.error) {
    const forbidden = progress.error instanceof ApiResponseError && progress.error.status === 403
    return (
      <PageLayout title="Прогресс">
        <PageStatePanel
          {...(!forbidden
            ? { actionLabel: 'Повторить', onAction: () => void progress.refetch() }
            : {})}
          state={
            forbidden
              ? 'forbidden'
              : progress.error instanceof CourseNetworkError
                ? 'offline'
                : 'error'
          }
        />
      </PageLayout>
    )
  }

  const view = toCourseEnrollmentView(enrollment)
  return (
    <PageLayout
      description="Только ваша личная работа. Здесь нет рейтинга и сравнения с другими школьниками."
      title="Прогресс"
    >
      <div className="space-y-5">
        <CourseContext
          activeCourseId={view.course.id}
          courses={courses.data.enrollments.map((item) => toCourseEnrollmentView(item).course)}
          onCourseChange={onCourseChange}
        />
        <Card>
          <CardContent className="pt-5">
            <StudentProgress
              attemptedCount={progress.data.summary.attempted}
              empty={progress.data.summary.attempted === 0}
              solvedCount={progress.data.summary.accepted}
            />
            {progress.data.summary.attempted > 0 ? (
              <p className="mt-3 text-small text-muted-foreground">
                Частично решено: {progress.data.summary.partial} · нужно вернуться:{' '}
                {progress.data.summary.needsWork} · ждут проверки:{' '}
                {progress.data.summary.awaitingReview}
              </p>
            ) : null}
          </CardContent>
        </Card>
        <PageSection title="По занятиям">
          {progress.data.lessons.length === 0 ? (
            <PageStatePanel state="empty" title="Пока нет проверенных задач" />
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border bg-surface">
              {progress.data.lessons.map((lesson) => (
                <li
                  className="flex items-center justify-between gap-4 px-3 py-2"
                  key={lesson.lessonNumber}
                >
                  <span className="font-medium">Занятие {lesson.lessonNumber}</span>
                  <span className="text-small text-muted-foreground">
                    {lesson.accepted} зачтено из {lesson.attempted}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </PageSection>
        {progress.data.analytics?.lessons.length ? (
          <PageSection title="Как получается решать задачи">
            <StrengthTrend
              caption="Ваша личная динамика по занятиям. С другими школьниками здесь не сравниваем."
              points={progress.data.analytics.lessons.map((lesson) => ({
                lesson: String(lesson.lessonNumber),
                simple: lesson.simpleStrength,
                complex: lesson.complexStrength,
                difficulty: lesson.maxComplexStrength,
                solved: `${lesson.solvedItems}/${lesson.totalItems}`,
                group: lesson.groupCode,
              }))}
            />
          </PageSection>
        ) : null}
        <PageSection title="Дни работы">
          {progress.data.activity.length === 0 ? (
            <p className="text-small text-muted-foreground">Отправок пока нет.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {progress.data.activity.map((day) => (
                <li
                  className="rounded-md border border-border bg-surface px-3 py-2 text-small"
                  key={day.date}
                >
                  {formatDate(day.date)} · {day.problemCount} задач
                </li>
              ))}
            </ul>
          )}
        </PageSection>
      </div>
    </PageLayout>
  )
}

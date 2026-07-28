import { useNavigate } from '@tanstack/react-router'
import { BookOpen, ChevronRight } from 'lucide-react'
import { useMemo } from 'react'

import {
  CourseNetworkError,
  PageLayout,
  PageSection,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentCoursesQuery,
  useStudentLessonArchiveQuery,
  type StudentCourseClient,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type CourseEnrollment,
  type PrincipalQueryScope,
  type StudentLessonSummary,
} from '@vmsh/contracts'
import { CourseContext, CourseGroupSwitcher } from '@vmsh/product'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

import { formatCalendarDate, problemCountLabel, toCourseEnrollmentView } from './student-home-view'
import {
  lessonHeading,
  publishedMaterialLabel,
  resolveStudentTasksContext,
  type StudentTasksSearch,
} from './student-tasks-view'

function requestState(error: unknown) {
  return error instanceof CourseNetworkError
    ? ('offline' as const)
    : error instanceof ApiResponseError && error.status === 403
      ? ('forbidden' as const)
      : ('error' as const)
}

function LessonCard({ lesson, onOpen }: { lesson: StudentLessonSummary; onOpen: () => void }) {
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-caption text-muted-foreground">
              Занятие {lesson.lessonNumber} · {formatCalendarDate(lesson.cycleAnchorDate)}
            </p>
            <CardTitle>{lessonHeading(lesson)}</CardTitle>
          </div>
          <Badge variant="neutral">{publishedMaterialLabel(lesson)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        <p className="inline-flex items-center gap-2 text-small text-muted-foreground">
          <BookOpen aria-hidden="true" className="size-4" />
          {problemCountLabel(lesson.problemCount)}
        </p>
        <Button onClick={onOpen} size="sm" variant="outline">
          Открыть листок
          <ChevronRight aria-hidden="true" />
        </Button>
      </CardContent>
    </Card>
  )
}

function StudentLessonArchive({
  client,
  principal,
  enrollments,
  enrollment,
  groupId,
  search,
}: {
  client: StudentCourseClient
  principal: PrincipalQueryScope
  enrollments: CourseEnrollment[]
  enrollment: CourseEnrollment
  groupId: string
  search: StudentTasksSearch
}) {
  const navigate = useNavigate({ from: '/tasks/' })
  const query = useStudentLessonArchiveQuery(client, principal, enrollment.course.courseId, groupId)
  const enrollmentView = toCourseEnrollmentView(enrollment)

  if (query.isPending) return <PageStatePanel state="loading" />
  if (query.error) {
    const state = requestState(query.error)
    return (
      <PageStatePanel
        {...(state === 'error' || state === 'offline'
          ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
          : {})}
        state={state}
      />
    )
  }

  const lessons = query.data.pages.flatMap((page) => page.lessons)
  const visibleLessons = search.lesson
    ? lessons.filter((lesson) => lesson.lessonNumber === search.lesson)
    : lessons

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <CourseContext
          activeCourseId={enrollment.course.courseId}
          courses={enrollments.map((candidate) => toCourseEnrollmentView(candidate).course)}
          onCourseChange={(courseId) => {
            void navigate({ search: { course: courseId }, replace: true })
          }}
        />
        <label className="grid min-w-0 gap-1 text-label font-medium text-foreground">
          <span>Занятие</span>
          <select
            className="min-h-(--touch-target) min-w-0 rounded-md border border-input bg-surface px-3 text-small"
            onChange={(event) => {
              const lesson = event.target.value ? Number(event.target.value) : undefined
              void navigate({
                search: {
                  course: enrollment.course.courseId,
                  group: groupId,
                  ...(lesson === undefined ? {} : { lesson }),
                },
                replace: true,
              })
            }}
            value={search.lesson ?? ''}
          >
            <option value="">Все опубликованные занятия</option>
            {lessons.map((lesson) => (
              <option key={lesson.groupLessonId} value={lesson.lessonNumber}>
                {lesson.lessonNumber} · {formatCalendarDate(lesson.cycleAnchorDate)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <CourseGroupSwitcher
        activeGroupId={groupId}
        course={enrollmentView.course}
        groups={enrollmentView.allowedGroups}
        helpText="Можно читать опубликованные листки всех доступных вам групп. Активная группа курса от этого не меняется."
        onChange={(nextGroupId) => {
          void navigate({
            search: { course: enrollment.course.courseId, group: nextGroupId },
            replace: true,
          })
        }}
      />

      <PageSection
        description={`${visibleLessons.length} из ${lessons.length} загруженных занятий`}
        title={search.lesson ? `Занятие ${search.lesson}` : 'Опубликованные занятия'}
      >
        {visibleLessons.length === 0 ? (
          <PageStatePanel
            description={
              search.lesson
                ? 'В загруженном архиве этой группы такого опубликованного занятия нет.'
                : 'После публикации условия листок появится здесь.'
            }
            state="empty"
            title={search.lesson ? 'Занятие не найдено' : 'Пока нет опубликованных листков'}
          />
        ) : (
          <div className="space-y-2">
            {visibleLessons.map((lesson) => (
              <LessonCard
                key={lesson.groupLessonId}
                lesson={lesson}
                onOpen={() => {
                  void navigate({
                    to: '/tasks/$taskId',
                    params: { taskId: `lesson-${lesson.lessonNumber}` },
                    search: { groupLesson: lesson.groupLessonId, material: 'condition' },
                  })
                }}
              />
            ))}
          </div>
        )}
        {query.hasNextPage ? (
          <Button
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
            size="sm"
            variant="ghost"
          >
            {query.isFetchingNextPage ? 'Загружаем…' : 'Показать более ранние занятия'}
          </Button>
        ) : null}
      </PageSection>
    </div>
  )
}

/** Production Student Tasks/archive boundary from Phase 3. */
export function StudentTasksArchivePage({ search }: { search: StudentTasksSearch }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student tasks require a Student principal')
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
  const accessQuery = useStudentCoursesQuery(client, {
    audience: 'student',
    accountId: principal.accountId,
  })

  let content
  if (accessQuery.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (accessQuery.error) {
    const state = requestState(accessQuery.error)
    content = (
      <PageStatePanel
        {...(state === 'error' || state === 'offline'
          ? { actionLabel: 'Повторить', onAction: () => void accessQuery.refetch() }
          : {})}
        state={state}
      />
    )
  } else {
    const context = resolveStudentTasksContext(accessQuery.data, search)
    content =
      context.kind === 'empty' ? (
        <PageStatePanel
          description="Когда вас добавят на курс, здесь появятся опубликованные листки."
          state="empty"
          title="Нет доступных курсов"
        />
      ) : context.kind === 'forbidden' ? (
        <PageStatePanel
          description="Выберите курс и группу из тех, которые доступны вашей учётной записи."
          state="forbidden"
        />
      ) : (
        <StudentLessonArchive
          client={client}
          enrollment={context.enrollment}
          enrollments={accessQuery.data.enrollments}
          groupId={context.groupId}
          principal={{ audience: 'student', accountId: principal.accountId }}
          search={search}
        />
      )
  }

  return (
    <PageLayout
      description="Опубликованные листки вашей активной и других доступных групп."
      eyebrow="Курс, группа и занятие"
      title="Задачи"
    >
      {content}
    </PageLayout>
  )
}

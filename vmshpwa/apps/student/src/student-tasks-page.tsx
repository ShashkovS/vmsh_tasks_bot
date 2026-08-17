import { useNavigate } from '@tanstack/react-router'
import { BookOpen, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  CourseNetworkError,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentCoursesQuery,
  useStudentLessonArchiveQuery,
  useStudentProblemsQuery,
  type StudentCourseClient,
} from '@vmsh/app-shell'
import {
  ContentNetworkError,
  SemanticMathDocument,
  createContentApiClient,
  usePublishedContentQuery,
} from '@vmsh/content'
import {
  ApiResponseError,
  type CourseEnrollment,
  type PrincipalQueryScope,
  type StudentLessonSummary,
  type StudentProblemSummary,
  type WebContentBlock,
  type WebContentProblem,
} from '@vmsh/contracts'
import { useOfflineDatabase } from '@vmsh/offline'
import { CourseContext, CourseGroupSwitcher } from '@vmsh/product'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

import { formatCalendarDate, problemCountLabel, toCourseEnrollmentView } from './student-home-view'
import {
  lessonHeading,
  publishedMaterialLabel,
  resolveStudentTasksContext,
  type StudentTasksSearch,
} from './student-tasks-view'
import {
  createOfflineStudentCourseClient,
  createOfflineStudentPublishedContentClient,
} from './offline-student-data'
import { ProblemStatusBadge, StudentTaskMaterials } from './student-task-detail-page'

function requestState(error: unknown) {
  return error instanceof CourseNetworkError
    ? ('offline' as const)
    : error instanceof ApiResponseError && error.status === 403
      ? ('forbidden' as const)
      : ('error' as const)
}

function containsSubpart(blocks: WebContentBlock[]): boolean {
  return blocks.some((block) => {
    if (block.type === 'subpart') return true
    if (block.type === 'callout') return containsSubpart(block.blocks)
    if (block.type === 'list') return block.items.some(containsSubpart)
    return false
  })
}

function subpartProblem(
  problems: StudentProblemSummary[],
  documentProblem: WebContentProblem,
  label: string,
): StudentProblemSummary | undefined {
  return problems.find(
    (problem) =>
      problem.sourceOrdinal === documentProblem.ordinal && problem.displayNumber.endsWith(label),
  )
}

function StudentLessonFeedItem({
  client,
  principal,
  enrollment,
  groupId,
  lesson,
}: {
  client: StudentCourseClient
  principal: PrincipalQueryScope
  enrollment: CourseEnrollment
  groupId: string
  lesson: StudentLessonSummary
}) {
  const navigate = useNavigate({ from: '/tasks/' })
  const authentication = useAuthentication()
  const database = useOfflineDatabase()
  const contentClient = useMemo(() => {
    const online = createContentApiClient(authentication.client.runtime, {
      refreshSession: async () => {
        try {
          return await authentication.refresh()
        } catch (error) {
          authentication.handleApiError(error)
          throw error
        }
      },
    })
    return createOfflineStudentPublishedContentClient(online, database, principal.accountId)
  }, [authentication, database, principal.accountId])
  const problemsQuery = useStudentProblemsQuery(
    client,
    principal,
    enrollment.course.courseId,
    groupId,
    lesson.groupLessonId,
  )
  const contentQuery = usePublishedContentQuery(
    contentClient,
    principal,
    { groupLessonId: lesson.groupLessonId, kind: 'condition' },
    { enabled: true },
  )
  const group = enrollment.allowedGroups.find((candidate) => candidate.groupId === groupId)

  if (problemsQuery.isPending || contentQuery.isPending) return <PageStatePanel state="loading" />
  if (problemsQuery.error || contentQuery.error) {
    const error = problemsQuery.error ?? contentQuery.error
    const state = error instanceof ContentNetworkError ? ('offline' as const) : requestState(error)
    return (
      <PageStatePanel
        {...(state === 'error' || state === 'offline'
          ? {
              actionLabel: 'Повторить',
              onAction: () => {
                void problemsQuery.refetch()
                void contentQuery.refetch()
              },
            }
          : {})}
        state={state}
      />
    )
  }
  if (!group) {
    return <PageStatePanel state="forbidden" />
  }

  const openProblem = (displayNumber: string) => {
    void navigate({
      to: '/tasks/$courseCode/$groupCode/$lessonNumber',
      params: {
        courseCode: enrollment.course.code,
        groupCode: group.code,
        lessonNumber: String(lesson.lessonNumber),
      },
      search: { task: displayNumber },
    })
  }

  const problemActions = (problem: StudentProblemSummary) => (
    <div className="flex items-center gap-2 font-sans">
      <ProblemStatusBadge problem={problem} />
      <Button
        aria-label={`Открыть задачу ${problem.displayNumber}`}
        onClick={() => openProblem(problem.displayNumber)}
        size="sm"
        variant="ghost"
      >
        Открыть
        <ChevronRight aria-hidden="true" />
      </Button>
    </div>
  )

  const problemsFor = (documentProblem: WebContentProblem) =>
    problemsQuery.data.problems.filter(
      (problem) => problem.sourceOrdinal === documentProblem.ordinal,
    )

  return (
    <Card className="overflow-hidden">
      <CardHeader className="gap-2 border-b border-border bg-surface-subtle">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-caption text-muted-foreground">
              Занятие {lesson.lessonNumber} · {formatCalendarDate(lesson.cycleAnchorDate)}
            </p>
            <CardTitle>{lessonHeading(lesson)}</CardTitle>
          </div>
          <Badge variant="neutral">{publishedMaterialLabel(lesson)}</Badge>
        </div>
        <p className="inline-flex items-center gap-2 text-small text-muted-foreground">
          <BookOpen aria-hidden="true" className="size-4" />
          {problemCountLabel(lesson.problemCount)}
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <SemanticMathDocument
          className="vmsh-student-feed-sheet px-5 py-6 sm:px-10 sm:py-8"
          document={contentQuery.data.document}
          renderAfterSubpart={(documentProblem, label) => {
            const problem = subpartProblem(problemsQuery.data.problems, documentProblem, label)
            return problem ? (
              <StudentTaskMaterials
                compact
                groupLessonId={lesson.groupLessonId}
                problem={problem}
              />
            ) : null
          }}
          renderAfterProblem={(documentProblem) => {
            if (containsSubpart(documentProblem.blocks)) return null
            const problems = problemsFor(documentProblem)
            if (problems.length === 0) return null
            return (
              <div className="space-y-2">
                {problems.map((problem) => (
                  <div key={problem.problemId}>
                    <StudentTaskMaterials
                      compact
                      groupLessonId={lesson.groupLessonId}
                      problem={problem}
                    />
                  </div>
                ))}
              </div>
            )
          }}
          renderProblemActions={(documentProblem) => {
            if (containsSubpart(documentProblem.blocks)) return null
            const problems = problemsFor(documentProblem)
            return problems.length === 1 && problems[0] ? problemActions(problems[0]) : null
          }}
          renderSubpartActions={(documentProblem, label) => {
            const problem = subpartProblem(problemsQuery.data.problems, documentProblem, label)
            return problem ? problemActions(problem) : null
          }}
        />
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
}: {
  client: StudentCourseClient
  principal: PrincipalQueryScope
  enrollments: CourseEnrollment[]
  enrollment: CourseEnrollment
  groupId: string
}) {
  const navigate = useNavigate({ from: '/tasks/' })
  const query = useStudentLessonArchiveQuery(client, principal, enrollment.course.courseId, groupId)
  const [visibleLessonCount, setVisibleLessonCount] = useState(5)
  const enrollmentView = toCourseEnrollmentView(enrollment)
  const selectedGroup = enrollment.allowedGroups.find((candidate) => candidate.groupId === groupId)

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
  if (!selectedGroup) return <PageStatePanel state="forbidden" />

  const lessons = query.data.pages.flatMap((page) => page.lessons)
  const visibleLessons = lessons.slice(0, visibleLessonCount)

  return (
    <div className="space-y-5">
      {enrollments.length > 1 ? (
        <CourseContext
          activeCourseId={enrollment.course.courseId}
          courses={enrollments.map((candidate) => toCourseEnrollmentView(candidate).course)}
          onCourseChange={(courseId) => {
            void navigate({ search: { course: courseId }, replace: true })
          }}
        />
      ) : null}

      <CourseGroupSwitcher
        activeGroupId={groupId}
        course={enrollmentView.course}
        groups={enrollmentView.allowedGroups}
        helpText={null}
        onChange={(nextGroupId) => {
          void navigate({
            search: { course: enrollment.course.courseId, group: nextGroupId },
            replace: true,
          })
        }}
      />

      <div>
        {visibleLessons.length === 0 ? (
          <PageStatePanel
            description={'После публикации условия листок появится здесь.'}
            state="empty"
            title="Пока нет опубликованных листков"
          />
        ) : (
          <div className="space-y-6">
            {visibleLessons.map((lesson) => (
              <StudentLessonFeedItem
                client={client}
                enrollment={enrollment}
                groupId={groupId}
                key={lesson.groupLessonId}
                lesson={lesson}
                principal={principal}
              />
            ))}
          </div>
        )}
        {visibleLessonCount < lessons.length || query.hasNextPage ? (
          <Button
            disabled={query.isFetchingNextPage}
            onClick={() => {
              if (visibleLessonCount < lessons.length) {
                setVisibleLessonCount((current) => current + 5)
              } else {
                void query
                  .fetchNextPage()
                  .then(() => setVisibleLessonCount((current) => current + 5))
              }
            }}
            size="sm"
            variant="ghost"
          >
            {query.isFetchingNextPage ? 'Загружаем…' : 'Показать более ранние занятия'}
          </Button>
        ) : null}
      </div>
    </div>
  )
}

/** Production Student Tasks/archive boundary from Phase 3. */
export function StudentTasksArchivePage({ search }: { search: StudentTasksSearch }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student tasks require a Student principal')
  const database = useOfflineDatabase()
  const client = useMemo(() => {
    const online = createStudentCourseClient(authentication.client.runtime, {
      refreshSession: async () => {
        try {
          return await authentication.refresh()
        } catch (error) {
          authentication.handleApiError(error)
          throw error
        }
      },
    })
    return createOfflineStudentCourseClient(online, database, principal.accountId)
  }, [authentication, database, principal.accountId])
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
          key={`${context.enrollment.course.courseId}:${context.groupId}`}
          principal={{ audience: 'student', accountId: principal.accountId }}
        />
      )
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-3 py-4 sm:px-5 2xl:-translate-x-28">{content}</div>
  )
}

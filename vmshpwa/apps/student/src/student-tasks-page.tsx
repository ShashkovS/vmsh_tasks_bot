import { studentWorksheetBindings } from './student-worksheet-bindings'
import { StudentReadStatePanel as PageStatePanel } from './student-read-state-panel'
import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import {
  rememberWorksheet,
  useWorksheetReturn,
  worksheetPageSizes,
  worksheetExpandedProblems,
} from './worksheet-return'

import { useNavigate } from '@tanstack/react-router'
import { BookOpen, ChevronRight, MessageCircleQuestion } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  CourseNetworkError,
  createStudentCourseClient,
  createSupportClient,
  useSupportAttentionQuery,
  useSupportThreadQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentCoursesQuery,
  useStudentLessonArchiveQuery,
  useStudentProblemsQuery,
  type StudentCourseClient,
} from '@vmsh/app-shell'
import {
  ContentNetworkError,
  WorksheetDocument,
  createContentApiClient,
  usePublishedContentQuery,
} from '@vmsh/content'
import {
  ApiResponseError,
  type CourseEnrollment,
  type PrincipalQueryScope,
  type StudentLessonSummary,
  type StudentProblemSummary,
  type SupportThread,
} from '@vmsh/contracts'
import { useOfflineDatabase } from '@vmsh/offline'
import { CourseContext, CourseGroupSwitcher, LessonBlocksLayout } from '@vmsh/product'
import { Badge, Button, Card, CardHeader, CardTitle } from '@vmsh/ui'

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
import {
  ProblemStatusBadge,
  STUDENT_SHEET_CONTAINER_CLASS,
  StudentProblemWorkspace,
} from './student-task-detail-page'

function requestState(error: unknown) {
  return error instanceof CourseNetworkError
    ? ('offline' as const)
    : error instanceof ApiResponseError && error.status === 403
      ? ('forbidden' as const)
      : ('error' as const)
}

/** One published worksheet as it appears in the Student tasks feed. */
export function StudentLessonFeedItem({
  client,
  principal,
  enrollment,
  groupId,
  lesson,
  targetQuestion,
  questionJumpAttempt,
}: {
  client: StudentCourseClient
  principal: PrincipalQueryScope
  enrollment: CourseEnrollment
  groupId: string
  lesson: StudentLessonSummary
  targetQuestion?: SupportThread | undefined
  questionJumpAttempt?: number | undefined
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
    lesson.materials.condition.status === 'published',
  )
  const contentQuery = usePublishedContentQuery(
    contentClient,
    principal,
    { groupLessonId: lesson.groupLessonId, kind: 'condition' },
    { enabled: lesson.materials.condition.status === 'published' },
  )
  const group = enrollment.allowedGroups.find((candidate) => candidate.groupId === groupId)
  const worksheetKey = `${principal.accountId}:${lesson.groupLessonId}`
  const [expandedProblemIds, setExpandedProblemIds] = useState<Set<string>>(
    () => worksheetExpandedProblems.get(worksheetKey) ?? new Set(),
  )
  useEffect(() => {
    worksheetExpandedProblems.set(worksheetKey, expandedProblemIds)
  }, [worksheetKey, expandedProblemIds])
  const [openedAt] = useState(() => Date.now())

  if (!group) return <PageStatePanel state="forbidden" />
  if (lesson.materials.condition.status !== 'published') {
    return (
      <section className="space-y-4" data-print-lesson>
        <Card className="overflow-hidden gap-0 py-0">
          <CardHeader className="gap-2 border-b border-border bg-surface-subtle">
            <p className="text-caption text-muted-foreground">
              <Trans>Занятие {lesson.lessonNumber} ·</Trans>{' '}
              {formatCalendarDate(lesson.cycleAnchorDate)}
            </p>
            <CardTitle>{lessonHeading(lesson)}</CardTitle>
          </CardHeader>
        </Card>
        <div>
          <LessonBlocksLayout
            after={lesson.blocks.after?.document ?? null}
            before={lesson.blocks.before?.document ?? null}
            idPrefix={`student-${lesson.groupLessonId}`}
          >
            <p className="px-4 py-5 text-muted-foreground sm:px-7">
              <Trans>Задачи ещё не опубликованы.</Trans>
            </p>
          </LessonBlocksLayout>
        </div>
      </section>
    )
  }

  if (problemsQuery.isPending || contentQuery.isPending) return <PageStatePanel state="loading" />
  if (problemsQuery.error || contentQuery.error) {
    const error = problemsQuery.error ?? contentQuery.error
    const state = error instanceof ContentNetworkError ? ('offline' as const) : requestState(error)
    return (
      <PageStatePanel
        {...(state === 'error' || state === 'offline'
          ? {
              actionLabel: t`Повторить`,
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
  const openProblem = (displayNumber: string, problemId: string) => {
    rememberWorksheet(problemId)
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

  // Status stays with the task number, the full-screen action stays at the
  // opposite edge; `.vmsh-problem-actions-row` owns that split in content.css.
  const problemActions = (problem: StudentProblemSummary) => (
    <span className="vmsh-problem-actions-row font-sans">
      <ProblemStatusBadge problem={problem} />
      <Button
        aria-label={t`Открыть задачу ${problem.displayNumber}`}
        data-task-return-id={problem.problemId}
        onClick={() => openProblem(problem.displayNumber, problem.problemId)}
        size="sm"
        variant="ghost"
      >
        <Trans>Открыть</Trans>
        <ChevronRight aria-hidden="true" />
      </Button>
    </span>
  )

  const submissionClosed = lesson.window
    ? openedAt >= Date.parse(lesson.window.submissionClosesAt)
    : false
  const toggleProblem = (problemId: string) =>
    setExpandedProblemIds((current) => {
      const next = new Set(current)
      if (next.has(problemId)) next.delete(problemId)
      else next.add(problemId)
      return next
    })
  const problemWorkspace = (problem: StudentProblemSummary) => (
    <StudentProblemWorkspace
      answerOpen={expandedProblemIds.has(problem.problemId)}
      conditionRevisionId={problemsQuery.data.conditionRevisionId}
      courseId={enrollment.course.courseId}
      groupLessonId={lesson.groupLessonId}
      targetQuestionId={
        targetQuestion?.context.problemId === problem.problemId
          ? targetQuestion.threadId
          : undefined
      }
      questionJumpAttempt={questionJumpAttempt}
      onToggleAnswer={() => toggleProblem(problem.problemId)}
      problem={problem}
      submissionClosed={submissionClosed}
    />
  )

  const answerableProblems = problemsQuery.data.problems.filter(
    (problem) => !submissionClosed || (problem.hasAnswer ?? problem.status !== 'not-started'),
  )
  const allExpanded =
    answerableProblems.length > 0 &&
    answerableProblems.every((problem) => expandedProblemIds.has(problem.problemId))

  return (
    <section className="space-y-4" data-print-lesson>
      <div>
        <LessonBlocksLayout
          after={lesson.blocks.after?.document ?? null}
          before={lesson.blocks.before?.document ?? null}
          idPrefix={`student-${lesson.groupLessonId}`}
        >
          <Card className="overflow-hidden gap-0 py-0">
            <CardHeader className="gap-2 border-b border-border bg-surface-subtle">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-caption text-muted-foreground">
                    <Trans>Занятие {lesson.lessonNumber} ·</Trans>{' '}
                    {formatCalendarDate(lesson.cycleAnchorDate)}
                  </p>
                  <CardTitle>{lessonHeading(lesson)}</CardTitle>
                </div>
                <div className="flex flex-wrap items-center gap-2" data-print-hide>
                  <Badge variant="neutral">{publishedMaterialLabel(lesson)}</Badge>
                  {answerableProblems.length > 0 ? (
                    <Button
                      onClick={() =>
                        setExpandedProblemIds(
                          allExpanded
                            ? new Set()
                            : new Set(answerableProblems.map((problem) => problem.problemId)),
                        )
                      }
                      size="sm"
                      variant="outline"
                    >
                      {allExpanded
                        ? t`Свернуть всё`
                        : submissionClosed
                          ? t`Показать все ответы`
                          : t`Ответить на все задачи`}
                    </Button>
                  ) : null}
                </div>
              </div>
              <p
                className="inline-flex items-center gap-2 text-small text-muted-foreground"
                data-print-hide
              >
                <BookOpen aria-hidden="true" className="size-4" />
                {problemCountLabel(lesson.problemCount)}
              </p>
            </CardHeader>
            <WorksheetDocument
              document={contentQuery.data.document}
              {...studentWorksheetBindings(
                problemsQuery.data.problems,
                problemWorkspace,
                problemActions,
              )}
            />
          </Card>
        </LessonBlocksLayout>
      </div>
    </section>
  )
}

function StudentLessonArchive({
  client,
  principal,
  enrollments,
  enrollment,
  groupId,
  targetQuestion,
  jumpAttempt,
}: {
  client: StudentCourseClient
  principal: PrincipalQueryScope
  targetQuestion?: SupportThread | undefined
  jumpAttempt: number
  enrollments: CourseEnrollment[]
  enrollment: CourseEnrollment
  groupId: string
}) {
  const navigate = useNavigate({ from: '/tasks/' })
  const query = useStudentLessonArchiveQuery(client, principal, enrollment.course.courseId, groupId)
  const archiveKey = `${JSON.stringify(principal)}:${enrollment.course.courseId}:${groupId}`
  const [visibleLessonCount, setVisibleLessonCount] = useState(
    () => worksheetPageSizes.get(archiveKey) ?? 5,
  )
  const targetLessonIndex =
    query.data?.pages
      .flatMap((page) => page.lessons)
      .findIndex((lesson) => lesson.groupLessonId === targetQuestion?.context.groupLessonId) ?? -1
  const effectiveVisibleLessonCount = Math.max(visibleLessonCount, targetLessonIndex + 1)
  useEffect(() => {
    worksheetPageSizes.set(archiveKey, effectiveVisibleLessonCount)
  }, [archiveKey, effectiveVisibleLessonCount])
  useWorksheetReturn(!targetQuestion)
  useEffect(() => {
    if (
      targetQuestion?.context.groupId === groupId &&
      targetLessonIndex < 0 &&
      query.hasNextPage &&
      !query.isFetchingNextPage
    )
      void query.fetchNextPage()
  }, [targetQuestion, groupId, targetLessonIndex, query])
  useQuestionAnswerScroll(targetQuestion, jumpAttempt)
  const enrollmentView = toCourseEnrollmentView(enrollment)
  const selectedGroup = enrollment.allowedGroups.find((candidate) => candidate.groupId === groupId)

  if (query.isPending) return <PageStatePanel state="loading" />
  if (query.error) {
    const state = requestState(query.error)
    return (
      <PageStatePanel
        {...(state === 'error' || state === 'offline'
          ? { actionLabel: t`Повторить`, onAction: () => void query.refetch() }
          : {})}
        state={state}
      />
    )
  }
  if (!selectedGroup) return <PageStatePanel state="forbidden" />

  const lessons = query.data.pages.flatMap((page) => page.lessons)
  const visibleLessons = lessons.slice(0, effectiveVisibleLessonCount)

  return (
    <div className="space-y-5">
      {enrollments.length > 1 ? (
        <CourseContext
          activeCourseId={enrollment.course.courseId}
          courses={enrollments.map((candidate) => toCourseEnrollmentView(candidate).course)}
          onCourseChange={(courseId) => {
            const nextEnrollment = enrollments.find(
              (candidate) => candidate.course.courseId === courseId,
            )
            if (!nextEnrollment) return
            void navigate({ search: { course: nextEnrollment.course.code }, replace: true })
          }}
        />
      ) : null}

      <CourseGroupSwitcher
        activeGroupId={groupId}
        course={enrollmentView.course}
        groups={enrollmentView.allowedGroups}
        helpText={null}
        onChange={(nextGroupId) => {
          const nextGroup = enrollment.allowedGroups.find(
            (candidate) => candidate.groupId === nextGroupId,
          )
          if (!nextGroup) return
          void navigate({
            search: { course: enrollment.course.code, group: nextGroup.code },
            replace: true,
          })
        }}
      />

      <div>
        {visibleLessons.length === 0 ? (
          <PageStatePanel
            description={t`После публикации условия листок появится здесь.`}
            state="empty"
            title={t`Пока нет опубликованных листков`}
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
                questionJumpAttempt={jumpAttempt}
                targetQuestion={
                  targetQuestion?.context.groupLessonId === lesson.groupLessonId
                    ? targetQuestion
                    : undefined
                }
              />
            ))}
          </div>
        )}
        {effectiveVisibleLessonCount < lessons.length || query.hasNextPage ? (
          <Button
            disabled={query.isFetchingNextPage}
            onClick={() => {
              if (effectiveVisibleLessonCount < lessons.length) {
                setVisibleLessonCount(
                  (current) => Math.max(current, effectiveVisibleLessonCount) + 5,
                )
              } else {
                void query
                  .fetchNextPage()
                  .then(() =>
                    setVisibleLessonCount(
                      (current) => Math.max(current, effectiveVisibleLessonCount) + 5,
                    ),
                  )
              }
            }}
            size="sm"
            variant="ghost"
          >
            {query.isFetchingNextPage ? t`Загружаем…` : t`Показать более ранние занятия`}
          </Button>
        ) : null}
      </div>
    </div>
  )
}

/** Production Student Tasks/archive boundary from Phase 3. */
export function StudentTasksArchivePage({ search }: { search: StudentTasksSearch }) {
  const navigate = useNavigate({ from: '/tasks/' })
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student tasks require a Student principal')
  const database = useOfflineDatabase()
  const supportClient = useMemo(
    () =>
      createSupportClient(authentication.client.runtime, {
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
  const attention = useSupportAttentionQuery(supportClient, principal, search.question)
  const targetQuestionQuery = useSupportThreadQuery(
    supportClient,
    principal,
    search.question ?? 'none',
    Boolean(search.question),
  )
  const [jumpAttempt, setJumpAttempt] = useState(0)
  const [jumpBusy, setJumpBusy] = useState(false)
  const [jumpError, setJumpError] = useState(false)
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

  useEffect(() => {
    const thread = targetQuestionQuery.data?.thread
    const enrollment = accessQuery.data?.enrollments.find(
      (item) => item.course.courseId === thread?.context.courseId,
    )
    const group = enrollment?.allowedGroups.find((item) => item.groupId === thread?.context.groupId)
    if (
      thread &&
      enrollment &&
      group &&
      (search.course !== enrollment.course.code || search.group !== group.code)
    ) {
      void navigate({
        search: { ...search, course: enrollment.course.code, group: group.code },
        replace: true,
      })
    }
  }, [accessQuery.data, navigate, search, targetQuestionQuery.data])
  const jumpToAnswer = async () => {
    setJumpBusy(true)
    setJumpError(false)
    try {
      const target = (await supportClient.attention(search.question)).nextTarget
      if (!target) {
        await attention.refetch()
        return
      }
      const enrollment = accessQuery.data?.enrollments.find(
        (item) => item.course.courseId === target.courseId,
      )
      const group = enrollment?.allowedGroups.find((item) => item.groupId === target.groupId)
      if (!enrollment || !group) throw new Error('Question target is outside current course access')
      await navigate({
        search: { course: enrollment.course.code, group: group.code, question: target.threadId },
      })
      setJumpAttempt((attempt) => attempt + 1)
    } catch (error) {
      authentication.handleApiError(error)
      setJumpError(true)
    } finally {
      setJumpBusy(false)
    }
  }

  const context = accessQuery.data
    ? resolveStudentTasksContext(accessQuery.data, search)
    : undefined
  useEffect(() => {
    if (context?.kind !== 'ready') return
    const selectedGroup = context.enrollment.allowedGroups.find(
      (group) => group.groupId === context.groupId,
    )
    if (!selectedGroup) return
    const canonicalCourse = context.enrollment.course.code
    const canonicalGroup = selectedGroup.code
    if (
      (search.course === undefined || search.course === canonicalCourse) &&
      (search.group === undefined || search.group === canonicalGroup)
    ) {
      return
    }
    void navigate({
      search: {
        ...search,
        ...(search.course === undefined ? {} : { course: canonicalCourse }),
        ...(search.group === undefined ? {} : { group: canonicalGroup }),
      },
      replace: true,
    })
  }, [context, navigate, search])

  let content
  if (accessQuery.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (accessQuery.error) {
    const state = requestState(accessQuery.error)
    content = (
      <PageStatePanel
        {...(state === 'error' || state === 'offline'
          ? { actionLabel: t`Повторить`, onAction: () => void accessQuery.refetch() }
          : {})}
        state={state}
      />
    )
  } else {
    const loadedContext = resolveStudentTasksContext(accessQuery.data, search)
    content =
      loadedContext.kind === 'empty' ? (
        <PageStatePanel
          description={t`Когда вас добавят на курс, здесь появятся опубликованные листки.`}
          state="empty"
          title={t`Нет доступных курсов`}
        />
      ) : loadedContext.kind === 'forbidden' ? (
        <PageStatePanel
          description={t`Выберите курс и группу из тех, которые доступны вашей учётной записи.`}
          state="forbidden"
        />
      ) : (
        <StudentLessonArchive
          client={client}
          enrollment={loadedContext.enrollment}
          enrollments={accessQuery.data.enrollments}
          groupId={loadedContext.groupId}
          key={`${loadedContext.enrollment.course.courseId}:${loadedContext.groupId}`}
          principal={{ audience: 'student', accountId: principal.accountId }}
          targetQuestion={targetQuestionQuery.data?.thread}
          jumpAttempt={jumpAttempt}
        />
      )
  }

  return (
    <div className={STUDENT_SHEET_CONTAINER_CLASS}>
      {(attention.data?.unreadTaskCount ?? 0) > 0 ? (
        <div className="mb-4 font-sans" data-print-hide>
          <Button
            disabled={jumpBusy || attention.isError}
            onClick={() => void jumpToAnswer()}
            variant="outline"
          >
            <MessageCircleQuestion aria-hidden="true" className="size-4" />
            <Trans>Новые ответы ({attention.data!.unreadTaskCount})</Trans>
          </Button>
        </div>
      ) : null}
      {jumpError || targetQuestionQuery.isError || attention.isError ? (
        <p className="mb-3 font-sans text-small text-danger" role="alert">
          <Trans>Не удалось загрузить новые ответы.</Trans>{' '}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setJumpError(false)
              void attention.refetch()
              if (search.question) void targetQuestionQuery.refetch()
            }}
          >
            <Trans>Повторить</Trans>
          </Button>
        </p>
      ) : null}
      {content}
    </div>
  )
}

/** docs/question-attention.md: wait for archive loading and inline dialogue mounting. */
function useQuestionAnswerScroll(thread: SupportThread | undefined, attempt: number) {
  const [completed, setCompleted] = useState('')
  useEffect(() => {
    if (!thread) return
    const key = `${thread.threadId}:${attempt}`
    if (completed === key) return
    const entryId =
      thread.firstUnreadEntryId ??
      thread.entries.filter((entry) => ['teacher', 'admin'].includes(entry.author.kind)).at(-1)
        ?.entryId
    if (!entryId) return
    let frame = 0
    const find = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const answer = document.querySelector<HTMLElement>(
          `[data-support-entry-id="${CSS.escape(entryId)}"]`,
        )
        if (!answer) return
        answer.scrollIntoView({
          block: 'start',
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
            ? 'instant'
            : 'smooth',
        })
        setCompleted(key)
      })
    }
    const observer = new MutationObserver(find)
    observer.observe(document.body, { childList: true, subtree: true })
    find()
    return () => {
      observer.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [thread, attempt, completed])
}

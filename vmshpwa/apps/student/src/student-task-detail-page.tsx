import { backToWorksheet } from './worksheet-return'

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { ArrowLeft, ChevronDown, ChevronUp, KeyRound, Lightbulb, PencilLine } from 'lucide-react'

import {
  CourseNetworkError,
  PageLayout,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentProblemsQuery,
} from '@vmsh/app-shell'
import { ContentNetworkError, SemanticMathDocument, createContentApiClient } from '@vmsh/content'
import {
  ApiResponseError,
  type StudentProblemReveal,
  type StudentProblemSummary,
  type StudentRevealKind,
} from '@vmsh/contracts'
import { useOfflineDatabase, type VmshOfflineDatabase } from '@vmsh/offline'
import { Badge, Button } from '@vmsh/ui'

import { StudentCollapseAction } from './student-collapse-action'
import { StudentPublishedContentPage } from './content-page'
import {
  createOfflineStudentCourseClient,
  readCachedStudentProblemReveal,
  revealStudentProblemMaterialWithOfflineCache,
} from './offline-student-data'
import { StudentTestAnswer } from './student-test-answer'
import { StudentWrittenSubmission } from './student-written-submission'
import { StudentProblemQuestionLink } from './student-support-pages'
import { StudentOralAdmission } from './student-oral-admission'

function problemRequestState(error: unknown) {
  return error instanceof CourseNetworkError || error instanceof ContentNetworkError
    ? ('offline' as const)
    : error instanceof ApiResponseError && error.status === 403
      ? ('forbidden' as const)
      : error instanceof ApiResponseError && error.status === 404
        ? ('empty' as const)
        : ('error' as const)
}

export function StudentTaskMaterials({
  problem,
  groupLessonId,
  compact = false,
}: {
  problem: StudentProblemSummary
  groupLessonId: string
  compact?: boolean
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') {
    throw new Error('Student material reveal requires a Student principal')
  }
  const database = useOfflineDatabase()
  const cacheIdentity = `${principal.accountId}:${groupLessonId}:${problem.problemId}`
  const client = useMemo(
    () =>
      createContentApiClient(authentication.client.runtime, {
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
  const [cachedMaterials, setCachedMaterials] = useState<{
    identity: string
    ready: boolean
    hint: StudentProblemReveal | null
    solution: StudentProblemReveal | null
  }>({ identity: '', ready: false, hint: null, solution: null })

  useEffect(() => {
    let active = true
    void Promise.all([
      problem.materials.hint.status === 'revealed'
        ? readCachedStudentProblemReveal(database, principal.accountId, {
            groupLessonId,
            problemId: problem.problemId,
            kind: 'hint',
          })
        : Promise.resolve(null),
      problem.materials.solution.status === 'revealed'
        ? readCachedStudentProblemReveal(database, principal.accountId, {
            groupLessonId,
            problemId: problem.problemId,
            kind: 'solution',
          })
        : Promise.resolve(null),
    ]).then(
      ([hint, solution]) => {
        if (active) setCachedMaterials({ identity: cacheIdentity, ready: true, hint, solution })
      },
      () => {
        if (active)
          setCachedMaterials({ identity: cacheIdentity, ready: true, hint: null, solution: null })
      },
    )
    return () => {
      active = false
    }
  }, [
    cacheIdentity,
    database,
    groupLessonId,
    principal.accountId,
    problem.materials.hint.status,
    problem.materials.solution.status,
    problem.problemId,
  ])

  if (!cachedMaterials.ready || cachedMaterials.identity !== cacheIdentity) return null

  return (
    <StudentTaskMaterialsReady
      key={cacheIdentity}
      client={client}
      database={database}
      groupLessonId={groupLessonId}
      initialHint={cachedMaterials.hint}
      initialSolution={cachedMaterials.solution}
      ownerId={principal.accountId}
      problem={problem}
      compact={compact}
    />
  )
}

function StudentProblemActions({
  conditionRevisionId,
  courseId,
  groupLessonId,
  problem,
  submissionClosed = false,
}: {
  conditionRevisionId: string
  courseId: string
  groupLessonId: string
  problem: StudentProblemSummary
  submissionClosed?: boolean
}) {
  return (
    <div className="mt-3 space-y-4 font-sans">
      {problem.type === 'test' ? (
        <StudentTestAnswer closed={submissionClosed} problemId={problem.problemId} />
      ) : null}
      {problem.type === 'oral' ? (
        <StudentOralAdmission courseId={courseId} groupLessonId={groupLessonId} />
      ) : null}
      {problem.type === 'written' || problem.type === 'oral' ? (
        <StudentWrittenSubmission
          conditionRevisionId={conditionRevisionId}
          configVersion={problem.configVersion}
          problemId={problem.problemId}
          problemType={problem.type}
          closed={submissionClosed}
        />
      ) : null}
    </div>
  )
}

/**
 * One action row per task: answering, questions, hint and solution all open in
 * place, inside the worksheet. Shared by the Student tasks feed and the
 * single-task page so both audiences see the same controls.
 */
export function StudentProblemWorkspace({
  answerOpen,
  conditionRevisionId,
  courseId,
  groupLessonId,
  onToggleAnswer,
  problem,
  submissionClosed = false,
}: {
  answerOpen: boolean
  conditionRevisionId: string
  courseId: string
  groupLessonId: string
  onToggleAnswer: () => void
  problem: StudentProblemSummary
  submissionClosed?: boolean
}) {
  return (
    <div className="vmsh-problem-workspace mt-2 flex flex-wrap items-center gap-1.5 font-sans">
      {!submissionClosed || (problem.hasAnswer ?? problem.status !== 'not-started') ? (
        <Button aria-expanded={answerOpen} onClick={onToggleAnswer} size="sm" variant="ghost">
          <PencilLine aria-hidden="true" className="size-4" />
          {submissionClosed ? 'Мой ответ' : 'Ответить'}
          {answerOpen ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
        </Button>
      ) : null}
      <StudentProblemQuestionLink
        compact
        groupLessonId={groupLessonId}
        problemId={problem.problemId}
      />
      <StudentTaskMaterials groupLessonId={groupLessonId} problem={problem} compact />
      {/*
       * Panels open below the whole button row, in button order: flex `order`
       * keeps the row intact instead of splitting it around an open panel.
       */}
      {answerOpen &&
      (!submissionClosed || (problem.hasAnswer ?? problem.status !== 'not-started')) ? (
        <div className="order-1 w-full basis-full" data-print-hide>
          <StudentProblemActions
            conditionRevisionId={conditionRevisionId}
            courseId={courseId}
            groupLessonId={groupLessonId}
            problem={problem}
            submissionClosed={submissionClosed}
          />
          <StudentCollapseAction label="Свернуть" onClick={onToggleAnswer} />
        </div>
      ) : null}
    </div>
  )
}

function StudentTaskMaterialsReady({
  client,
  database,
  groupLessonId,
  initialHint,
  initialSolution,
  ownerId,
  problem,
  compact,
}: {
  client: ReturnType<typeof createContentApiClient>
  database: VmshOfflineDatabase
  groupLessonId: string
  initialHint: StudentProblemReveal | null
  initialSolution: StudentProblemReveal | null
  ownerId: string
  problem: StudentProblemSummary
  compact: boolean
}) {
  const [hint, setHint] = useState<StudentProblemReveal | null>(initialHint)
  const [solution, setSolution] = useState<StudentProblemReveal | null>(initialSolution)
  const [openKind, setOpenKind] = useState<StudentRevealKind | null>(null)
  const [loadingKind, setLoadingKind] = useState<StudentRevealKind | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reveal = async (kind: StudentRevealKind) => {
    const existing = kind === 'hint' ? hint : solution
    const response =
      existing ??
      (await revealStudentProblemMaterialWithOfflineCache(
        client,
        database,
        ownerId,
        {
          groupLessonId,
          problemId: problem.problemId,
          kind,
        },
        problem.materials[kind].status === 'revealed',
      ))
    if (
      response.groupLessonId !== groupLessonId ||
      response.problemId !== problem.problemId ||
      response.kind !== kind
    ) {
      throw new Error('Reveal response does not match the requested task')
    }
    if (kind === 'hint') setHint(response)
    else setSolution(response)
  }

  const toggle = async (kind: StudentRevealKind) => {
    if (openKind === kind) {
      setOpenKind(null)
      return
    }
    setError(null)
    setOpenKind(kind)
    if ((kind === 'hint' ? hint : solution) !== null) return
    setLoadingKind(kind)
    try {
      await reveal(kind)
    } catch {
      setError('Не удалось открыть материал. Проверьте соединение и повторите попытку.')
    } finally {
      setLoadingKind(null)
    }
  }

  if (
    problem.materials.hint.status === 'unavailable' &&
    problem.materials.solution.status === 'unavailable'
  ) {
    return null
  }

  return (
    <section
      aria-label="Подсказка и решение"
      className={compact ? 'contents font-sans' : 'mt-4 font-sans'}
    >
      <div className={compact ? 'contents' : 'flex flex-wrap gap-1.5'}>
        {problem.materials.hint.status === 'unavailable' ? null : (
          <Button onClick={() => void toggle('hint')} size="sm" variant="ghost">
            <Lightbulb aria-hidden="true" className="size-4" />
            Подсказка
            {openKind === 'hint' ? (
              <ChevronUp aria-hidden="true" />
            ) : (
              <ChevronDown aria-hidden="true" />
            )}
          </Button>
        )}
        {problem.materials.solution.status === 'unavailable' ? null : (
          <Button onClick={() => void toggle('solution')} size="sm" variant="ghost">
            <KeyRound aria-hidden="true" className="size-4" />
            Решение
            {openKind === 'solution' ? (
              <ChevronUp aria-hidden="true" />
            ) : (
              <ChevronDown aria-hidden="true" />
            )}
          </Button>
        )}
      </div>
      {error ? (
        <p data-print-hide className="order-3 mt-2 w-full basis-full text-small text-danger">
          {error}
        </p>
      ) : null}
      {loadingKind !== null && loadingKind === openKind ? (
        <p
          data-print-hide
          className="order-3 mt-2 w-full basis-full text-small text-muted-foreground"
        >
          Загружаем…
        </p>
      ) : null}
      {openKind === 'hint' && hint ? (
        <div className="vmsh-material-reveal order-3 mt-2 w-full basis-full border-l-2 border-border pl-3">
          <span className="vmsh-print-material-label">Подсказка</span>
          <SemanticMathDocument document={hint.document} imageLoading="eager" />
          <StudentCollapseAction label="Скрыть подсказку" onClick={() => setOpenKind(null)} />
        </div>
      ) : null}
      {openKind === 'solution' && solution ? (
        <div className="vmsh-material-reveal order-3 mt-2 w-full basis-full border-l-2 border-border pl-3">
          <span className="vmsh-print-material-label">Решение</span>
          <SemanticMathDocument document={solution.document} imageLoading="eager" />
          <StudentCollapseAction label="Скрыть решение" onClick={() => setOpenKind(null)} />
        </div>
      ) : null}
    </section>
  )
}

/*
 * The tasks feed and the single-task page must place the paper identically, so
 * both use one container/sheet pair. See apps/student StudentTasksArchivePage.
 */
export const STUDENT_SHEET_CONTAINER_CLASS =
  'mx-auto w-full max-w-5xl px-3 py-4 sm:px-5 2xl:-translate-x-28'
export const STUDENT_SHEET_CLASS =
  'vmsh-student-sheet rounded-sm border border-border bg-surface px-5 py-6 shadow-sm sm:px-10 sm:py-8'

/**
 * Single task on its own page, opened from the "Открыть" action in the tasks
 * feed. Same sheet geometry as the feed card so the paper does not shift.
 */
export function CanonicalStudentTask({
  courseCode,
  courseId,
  groupCode,
  groupId,
  groupLessonId,
  taskId,
  submissionClosed = false,
}: {
  courseCode: string
  courseId: string
  groupCode: string
  groupId: string
  groupLessonId: string
  taskId: string
  submissionClosed?: boolean
}) {
  const authentication = useAuthentication()
  const navigate = useNavigate()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student task requires a Student principal')
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
  const query = useStudentProblemsQuery(
    client,
    { audience: 'student', accountId: principal.accountId },
    courseId,
    groupId,
    groupLessonId,
  )
  // Opening a single task is already the intent to work on it, so the answer
  // panel starts expanded; the same control still collapses it.
  const [answerOpen, setAnswerOpen] = useState(true)

  if (query.isPending) {
    return (
      <PageLayout title="Задача" width="reading">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    const state = problemRequestState(query.error)
    return (
      <PageLayout title="Задача" width="reading">
        <PageStatePanel
          {...(state === 'error' || state === 'offline'
            ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
            : {})}
          {...(state === 'empty' ? { title: 'Листок не найден' } : {})}
          state={state}
        />
      </PageLayout>
    )
  }
  if (
    query.data.courseId !== courseId ||
    query.data.groupId !== groupId ||
    query.data.groupLessonId !== groupLessonId
  ) {
    return (
      <PageLayout title="Задача" width="reading">
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }

  const problem = query.data.problems.find((candidate) => candidate.problemId === taskId)
  if (!problem) {
    return (
      <PageLayout title="Задача" width="reading">
        <PageStatePanel
          description="В текущей опубликованной версии листка такой задачи нет. Откройте её заново из списка задач."
          state="empty"
          title="Задача не найдена"
        />
      </PageLayout>
    )
  }

  return (
    <StudentPublishedContentPage
      beforeDocument={
        <div className="mb-4 flex justify-start border-b border-border pb-3 font-sans">
          <Button
            onClick={() =>
              !backToWorksheet() &&
              void navigate({
                to: '/tasks',
                search: { course: courseCode, group: groupCode },
              })
            }
            size="sm"
            variant="ghost"
          >
            <ArrowLeft aria-hidden="true" className="size-4" />К листку
          </Button>
        </div>
      }
      containerClassName={STUDENT_SHEET_CONTAINER_CLASS}
      documentClassName={STUDENT_SHEET_CLASS}
      groupLessonId={groupLessonId}
      hidePageHeading
      kind="condition"
      problemOrdinal={problem.sourceOrdinal}
      renderAfterProblem={() => (
        <StudentProblemWorkspace
          answerOpen={answerOpen}
          conditionRevisionId={query.data.conditionRevisionId}
          courseId={courseId}
          groupLessonId={groupLessonId}
          onToggleAnswer={() => setAnswerOpen((open) => !open)}
          problem={problem}
          submissionClosed={submissionClosed}
        />
      )}
      renderProblemActions={() => (
        <span className="vmsh-problem-actions-row font-sans">
          <ProblemStatusBadge problem={problem} />
        </span>
      )}
      taskId={problem.problemId}
    />
  )
}

const problemStatusView = {
  'not-started': { label: 'Не начата', variant: 'neutral' },
  sent: { label: 'Отправлено', variant: 'info' },
  checking: { label: 'На проверке', variant: 'info' },
  accepted: { label: 'Зачтено', variant: 'success' },
  'needs-work': { label: 'Нужна доработка', variant: 'warning' },
  rejected: { label: 'Ответ не принят', variant: 'danger' },
} as const

export function ProblemStatusBadge({ problem }: { problem: StudentProblemSummary }) {
  const view = problemStatusView[problem.status]
  return (
    <Badge variant={view.variant}>
      {problem.verdict ? `${problem.verdict.symbol} ` : ''}
      {view.label}
    </Badge>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, KeyRound, Lightbulb } from 'lucide-react'

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
  type WebContentProblem,
} from '@vmsh/contracts'
import { useOfflineDatabase, type VmshOfflineDatabase } from '@vmsh/offline'
import { Badge, Button } from '@vmsh/ui'

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

function StudentProblemMaterialsAndQuestion({
  groupLessonId,
  problem,
}: {
  groupLessonId: string
  problem: StudentProblemSummary
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 font-sans">
      <StudentProblemQuestionLink
        compact
        groupLessonId={groupLessonId}
        problemId={problem.problemId}
      />
      <StudentTaskMaterials groupLessonId={groupLessonId} problem={problem} compact />
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
      {error ? <p className="mt-2 w-full basis-full text-small text-danger">{error}</p> : null}
      {loadingKind === openKind ? (
        <p className="mt-2 w-full basis-full text-small text-muted-foreground">Загружаем…</p>
      ) : null}
      {openKind === 'hint' && hint ? (
        <div className="vmsh-material-reveal mt-2 w-full basis-full border-l-2 border-border pl-3">
          <SemanticMathDocument document={hint.document} />
        </div>
      ) : null}
      {openKind === 'solution' && solution ? (
        <div className="vmsh-material-reveal mt-2 w-full basis-full border-l-2 border-border pl-3">
          <SemanticMathDocument document={solution.document} />
        </div>
      ) : null}
    </section>
  )
}

export function CanonicalStudentTask({
  courseId,
  groupId,
  groupLessonId,
  taskId,
  submissionClosed = false,
}: {
  courseId: string
  groupId: string
  groupLessonId: string
  taskId: string
  submissionClosed?: boolean
}) {
  const authentication = useAuthentication()
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
      afterDocument={
        <section aria-label="Ответы и обсуждение" className="mx-auto mt-3 max-w-[96ch]">
          <StudentProblemActions
            conditionRevisionId={query.data.conditionRevisionId}
            courseId={courseId}
            groupLessonId={groupLessonId}
            problem={problem}
            submissionClosed={submissionClosed}
          />
          <StudentProblemMaterialsAndQuestion groupLessonId={groupLessonId} problem={problem} />
        </section>
      }
      documentClassName="vmsh-student-sheet mx-auto max-w-[96ch] rounded-sm border border-border bg-surface px-4 py-5 shadow-sm sm:px-7 sm:py-7"
      groupLessonId={groupLessonId}
      hidePageHeading
      kind="condition"
      pageWidth="content"
      problemOrdinal={problem.sourceOrdinal}
      renderProblemActions={() => <ProblemStatusBadge problem={problem} />}
      taskId={problem.problemId}
    />
  )
}

export function CanonicalStudentWorksheet({
  courseId,
  groupId,
  groupLessonId,
  taskId,
  displayTitle,
  submissionClosed = false,
}: {
  courseId: string
  groupId: string
  groupLessonId: string
  taskId: string
  displayTitle?: string
  submissionClosed?: boolean
}) {
  const authentication = useAuthentication()
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
  const [expandedProblemIds, setExpandedProblemIds] = useState<Set<string>>(() => new Set())

  if (query.isPending) {
    return (
      <PageLayout title="Листок" width="reading">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    const state = problemRequestState(query.error)
    return (
      <PageLayout title="Листок" width="reading">
        <PageStatePanel
          {...(state === 'error' || state === 'offline'
            ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
            : {})}
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
      <PageLayout title="Листок" width="reading">
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }

  const data = query.data
  const problemsFor = (documentProblem: WebContentProblem) =>
    data.problems.filter((problem) => problem.sourceOrdinal === documentProblem.ordinal)
  const problemForSubpart = (documentProblem: WebContentProblem, label: string) =>
    problemsFor(documentProblem).find((problem) =>
      problem.displayNumber.toLocaleLowerCase('ru-RU').endsWith(label.toLocaleLowerCase('ru-RU')),
    )
  const toggleProblem = (problemId: string) =>
    setExpandedProblemIds((current) => {
      const next = new Set(current)
      if (next.has(problemId)) next.delete(problemId)
      else next.add(problemId)
      return next
    })
  const inlineActions = (problem: StudentProblemSummary) => (
    <span className="vmsh-inline-problem-actions font-sans">
      <ProblemStatusBadge problem={problem} />
      <Button
        aria-expanded={expandedProblemIds.has(problem.problemId)}
        onClick={() => toggleProblem(problem.problemId)}
        size="sm"
        variant="ghost"
      >
        {expandedProblemIds.has(problem.problemId)
          ? 'Скрыть'
          : submissionClosed
            ? 'Посмотреть'
            : 'Ответить'}
      </Button>
    </span>
  )
  const afterProblem = (problem: StudentProblemSummary) => (
    <div className="mb-4">
      {expandedProblemIds.has(problem.problemId) ? (
        <StudentProblemActions
          conditionRevisionId={data.conditionRevisionId}
          courseId={courseId}
          groupLessonId={groupLessonId}
          problem={problem}
          submissionClosed={submissionClosed}
        />
      ) : null}
      <StudentProblemMaterialsAndQuestion groupLessonId={groupLessonId} problem={problem} />
    </div>
  )

  return (
    <StudentPublishedContentPage
      beforeDocument={
        <div className="mx-auto mb-2 flex max-w-[96ch] justify-end">
          <Button
            onClick={() =>
              setExpandedProblemIds((current) =>
                current.size === data.problems.length
                  ? new Set()
                  : new Set(data.problems.map((problem) => problem.problemId)),
              )
            }
            size="sm"
            variant="outline"
          >
            {expandedProblemIds.size === data.problems.length
              ? 'Свернуть всё'
              : submissionClosed
                ? 'Показать все отправленные ответы'
                : 'Ответить на все задачи'}
          </Button>
        </div>
      }
      {...(displayTitle === undefined ? {} : { displayTitle })}
      documentClassName="vmsh-student-sheet mx-auto max-w-[96ch] rounded-sm border border-border bg-surface px-4 py-5 shadow-sm sm:px-7 sm:py-7"
      groupLessonId={groupLessonId}
      hidePageHeading
      kind="condition"
      pageWidth="content"
      renderProblemActions={(documentProblem) => {
        const problems = problemsFor(documentProblem)
        const problem = problems[0]
        return problem && problems.length === 1 ? inlineActions(problem) : null
      }}
      renderSubpartActions={(documentProblem, label) => {
        const problem = problemForSubpart(documentProblem, label)
        return problem ? inlineActions(problem) : null
      }}
      renderAfterSubpart={(documentProblem, label) => {
        const problem = problemForSubpart(documentProblem, label)
        return problem ? afterProblem(problem) : null
      }}
      renderAfterProblem={(documentProblem) => {
        const problems = problemsFor(documentProblem)
        const problem = problems[0]
        return problem && problems.length === 1 ? afterProblem(problem) : null
      }}
      taskId={taskId}
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

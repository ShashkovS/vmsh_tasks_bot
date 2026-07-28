import { useEffect, useMemo, useState } from 'react'

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
  publicIdSchema,
  type StudentProblemReveal,
  type StudentProblemSummary,
  type StudentRevealKind,
} from '@vmsh/contracts'
import { useOfflineDatabase, type VmshOfflineDatabase } from '@vmsh/offline'
import { HintDisclosure, SolutionDisclosure } from '@vmsh/product'

import { StudentPublishedContentPage } from './content-page'
import {
  createOfflineStudentCourseClient,
  readCachedStudentProblemReveal,
  revealStudentProblemMaterialWithOfflineCache,
} from './offline-student-data'

function problemRequestState(error: unknown) {
  return error instanceof CourseNetworkError || error instanceof ContentNetworkError
    ? ('offline' as const)
    : error instanceof ApiResponseError && error.status === 403
      ? ('forbidden' as const)
      : error instanceof ApiResponseError && error.status === 404
        ? ('empty' as const)
        : ('error' as const)
}

function StudentTaskMaterials({
  problem,
  groupLessonId,
}: {
  problem: StudentProblemSummary
  groupLessonId: string
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
    />
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
}: {
  client: ReturnType<typeof createContentApiClient>
  database: VmshOfflineDatabase
  groupLessonId: string
  initialHint: StudentProblemReveal | null
  initialSolution: StudentProblemReveal | null
  ownerId: string
  problem: StudentProblemSummary
}) {
  const [hint, setHint] = useState<StudentProblemReveal | null>(initialHint)
  const [solution, setSolution] = useState<StudentProblemReveal | null>(initialSolution)

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

  if (
    problem.materials.hint.status === 'unavailable' &&
    problem.materials.solution.status === 'unavailable'
  ) {
    return null
  }

  return (
    <section aria-label="Подсказка и решение" className="mt-5 space-y-2">
      {problem.materials.hint.status === 'unavailable' ? null : (
        <HintDisclosure
          initiallyRevealed={problem.materials.hint.status === 'revealed' || hint !== null}
          meta={
            hint
              ? `опубликовано ${new Date(hint.publishedAt).toLocaleDateString('ru-RU')}`
              : undefined
          }
          onReveal={() => reveal('hint')}
        >
          {hint ? <SemanticMathDocument document={hint.document} /> : null}
        </HintDisclosure>
      )}
      {problem.materials.solution.status === 'unavailable' ? null : (
        <SolutionDisclosure
          initiallyRevealed={problem.materials.solution.status === 'revealed' || solution !== null}
          meta={
            solution
              ? `опубликовано ${new Date(solution.publishedAt).toLocaleDateString('ru-RU')}`
              : undefined
          }
          onReveal={() => reveal('solution')}
        >
          {solution ? <SemanticMathDocument document={solution.document} /> : null}
        </SolutionDisclosure>
      )}
    </section>
  )
}

function CanonicalStudentTask({
  courseId,
  groupId,
  groupLessonId,
  taskId,
}: {
  courseId: string
  groupId: string
  groupLessonId: string
  taskId: string
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
      afterDocument={<StudentTaskMaterials groupLessonId={groupLessonId} problem={problem} />}
      groupLessonId={groupLessonId}
      kind="condition"
      problemOrdinal={problem.sourceOrdinal}
      taskId={problem.problemId}
    />
  )
}

/** Resolves an opaque problem identity against the exact published list. */
export function StudentTaskDetailPage({
  taskId,
  courseId,
  groupId,
  groupLessonId,
  material,
  legacyProblemOrdinal,
}: {
  taskId: string
  courseId?: string
  groupId?: string
  groupLessonId?: string
  material: 'condition' | 'hint' | 'solution'
  legacyProblemOrdinal?: number
}) {
  const canonicalContext =
    publicIdSchema.safeParse(taskId).success &&
    courseId !== undefined &&
    groupId !== undefined &&
    groupLessonId !== undefined &&
    material === 'condition'

  if (canonicalContext) {
    return (
      <CanonicalStudentTask
        courseId={courseId}
        groupId={groupId}
        groupLessonId={groupLessonId}
        taskId={taskId}
      />
    )
  }

  return (
    <StudentPublishedContentPage
      kind={material}
      taskId={taskId}
      {...(groupLessonId ? { groupLessonId } : {})}
      {...(legacyProblemOrdinal ? { problemOrdinal: legacyProblemOrdinal } : {})}
    />
  )
}

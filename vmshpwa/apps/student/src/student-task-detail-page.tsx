import { useMemo, useState } from 'react'

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
import { HintDisclosure, SolutionDisclosure } from '@vmsh/product'

import { StudentPublishedContentPage } from './content-page'

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
  const [hint, setHint] = useState<StudentProblemReveal | null>(null)
  const [solution, setSolution] = useState<StudentProblemReveal | null>(null)

  const reveal = async (kind: StudentRevealKind) => {
    const response = await client.revealStudentProblemMaterial({
      groupLessonId,
      problemId: problem.problemId,
      kind,
    })
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
          initiallyRevealed={problem.materials.hint.status === 'revealed'}
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
          initiallyRevealed={problem.materials.solution.status === 'revealed'}
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

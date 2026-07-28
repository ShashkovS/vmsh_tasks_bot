import { useMemo } from 'react'

import {
  CourseNetworkError,
  PageLayout,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentProblemsQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, publicIdSchema } from '@vmsh/contracts'

import { StudentPublishedContentPage } from './content-page'

function problemRequestState(error: unknown) {
  return error instanceof CourseNetworkError
    ? ('offline' as const)
    : error instanceof ApiResponseError && error.status === 403
      ? ('forbidden' as const)
      : error instanceof ApiResponseError && error.status === 404
        ? ('empty' as const)
        : ('error' as const)
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

import { useMemo } from 'react'
import { useNavigate } from '@tanstack/react-router'

import {
  createFamilyCourseClient,
  PageLayout,
  PageStatePanel,
  useAuthenticatedPrincipal,
  useAuthentication,
  useFamilyChildCoursesQuery,
  useFamilyWorksheetQuery,
} from '@vmsh/app-shell'
import {
  ContentNetworkError,
  SemanticMathDocument,
  createContentApiClient,
  usePublishedContentReplacement,
  usePublishedContentQuery,
} from '@vmsh/content'
import {
  ApiResponseError,
  type ContentMaterialKind,
  type StudentProblemSummary,
  type CourseEnrollment,
  type WebContentBlock,
} from '@vmsh/contracts'
import { ContentUpdateMarker } from '@vmsh/product'
import { Badge } from '@vmsh/ui'

function hasSubparts(blocks: WebContentBlock[]): boolean {
  return blocks.some(
    (block) =>
      block.type === 'subpart' ||
      ('blocks' in block && hasSubparts(block.blocks)) ||
      (block.type === 'list' && block.items.some(hasSubparts)),
  )
}

const materialLabels: Record<ContentMaterialKind, string> = {
  condition: 'Условие',
  hint: 'Подсказка',
  solution: 'Решение',
}

/** Family uses the same published derivative but always keeps child ownership explicit. */
export function FamilyPublishedContentPage({
  taskId,
  groupLessonId,
  kind,
  requestedStudentPublicId,
  problemOrdinal,
  displayTitle,
}: {
  taskId: string
  groupLessonId?: string
  kind: ContentMaterialKind
  requestedStudentPublicId?: string
  problemOrdinal?: number
  displayTitle?: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') {
    throw new Error('Family content requires a Family principal')
  }
  const linkedChildren = principal.linkedChildren
  const studentPublicId =
    requestedStudentPublicId ??
    linkedChildren.find((child) => child.isPrimary)?.studentId ??
    linkedChildren[0]?.studentId
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
  const query = usePublishedContentQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    {
      groupLessonId: groupLessonId ?? 'missing',
      kind,
      studentPublicId: studentPublicId ?? 'missing',
    },
    { enabled: groupLessonId !== undefined && studentPublicId !== undefined },
  )
  const contentWasReplaced = usePublishedContentReplacement(
    groupLessonId && studentPublicId
      ? `family:${studentPublicId}:${groupLessonId}:${kind}`
      : undefined,
    query.data?.revisionId,
  )

  if (!groupLessonId || !studentPublicId) {
    return (
      <PageLayout title={`Задача ${taskId}`} width="reading">
        <PageStatePanel
          description={
            !studentPublicId
              ? 'У семейного аккаунта нет доступного профиля ребёнка.'
              : 'Откройте задачу из опубликованного листка ребёнка.'
          }
          state="empty"
          title={!studentPublicId ? 'Не выбран ребёнок' : 'Не указан опубликованный листок'}
        />
      </PageLayout>
    )
  }
  if (query.isPending) {
    return (
      <PageLayout title={materialLabels[kind]} width="reading">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    const error = query.error
    const state =
      error instanceof ContentNetworkError
        ? 'offline'
        : error instanceof ApiResponseError && error.status === 403
          ? 'forbidden'
          : error instanceof ApiResponseError && error.status === 404
            ? 'empty'
            : 'error'
    return (
      <PageLayout title={materialLabels[kind]} width="reading">
        <PageStatePanel
          {...(state === 'error' || state === 'offline'
            ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
            : {})}
          {...(state === 'empty'
            ? {
                description: 'Этот материал ещё не опубликован для выбранной группы ребёнка.',
              }
            : {})}
          description="Не удалось загрузить материал. Попробуйте ещё раз."
          state={state}
          {...(state === 'empty' ? { title: 'Материал пока закрыт' } : {})}
        />
      </PageLayout>
    )
  }

  const document = query.data.document
  const selectedProblem =
    problemOrdinal === undefined
      ? undefined
      : document.problems.find((problem) => problem.ordinal === problemOrdinal)
  if (problemOrdinal !== undefined && !selectedProblem) {
    return (
      <PageLayout title={document.title ?? materialLabels[kind]} width="reading">
        <PageStatePanel state="empty" title="Задача не найдена" />
      </PageLayout>
    )
  }
  const visibleDocument = selectedProblem
    ? { ...document, introduction: [], problems: [selectedProblem] }
    : document

  return (
    <PageLayout
      eyebrow={materialLabels[kind]}
      title={
        selectedProblem
          ? `Задача ${selectedProblem.taskReference ?? selectedProblem.ordinal}.${selectedProblem.title ? ` «${selectedProblem.title}»` : ''}`
          : (displayTitle ?? document.title ?? materialLabels[kind])
      }
      width={selectedProblem ? 'reading' : 'content'}
    >
      <ContentUpdateMarker visible={contentWasReplaced} />
      <div className="mx-auto w-full max-w-5xl">
        <SemanticMathDocument
          {...(selectedProblem
            ? {}
            : {
                className:
                  'vmsh-student-sheet rounded-xl border border-border bg-surface px-4 py-5 shadow-sm sm:px-7 sm:py-6',
              })}
          document={visibleDocument}
        />
      </div>
    </PageLayout>
  )
}

/** Resolve the public lesson from readable course/group/lesson coordinates. */
export function FamilyReadableContentPage({
  childNumber,
  courseCode,
  groupCode,
  lessonNumber,
}: {
  childNumber?: number
  courseCode: string
  groupCode: string
  lessonNumber: number
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') {
    throw new Error('Family content requires a Family principal')
  }
  const fallbackChild =
    principal.linkedChildren.find((child) => child.isPrimary) ?? principal.linkedChildren[0]
  const selectedChild =
    childNumber === undefined ? fallbackChild : principal.linkedChildren[childNumber - 1]
  const client = useMemo(
    () =>
      createFamilyCourseClient(authentication.client.runtime, {
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
  const query = useFamilyChildCoursesQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    selectedChild?.studentId ?? 'missing',
    selectedChild !== undefined,
  )

  if (!selectedChild) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel state="empty" title="Не выбран ребёнок" />
      </PageLayout>
    )
  }
  if (query.isPending) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void query.refetch()}
          state="error"
          description="Не удалось загрузить данные ребёнка. Попробуйте ещё раз."
        />
      </PageLayout>
    )
  }
  const course = query.data.enrollments.find(
    (enrollment) =>
      enrollment.course.code.toLocaleLowerCase('ru-RU') === courseCode.toLocaleLowerCase('ru-RU'),
  )
  const group = course?.allowedGroups.find(
    (candidate) =>
      candidate.code.toLocaleLowerCase('ru-RU') === groupCode.toLocaleLowerCase('ru-RU'),
  )
  if (!course || !group) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel state="forbidden" description="Эта группа недоступна выбранному ребёнку." />
      </PageLayout>
    )
  }
  return (
    <FamilyWorksheet
      client={client}
      studentId={selectedChild.studentId}
      course={course}
      groupId={group.groupId}
      lessonNumber={lessonNumber}
      childNumber={childNumber}
    />
  )
}

function FamilyWorksheet({
  client,
  studentId,
  course,
  groupId,
  lessonNumber,
  childNumber,
}: {
  client: ReturnType<typeof createFamilyCourseClient>
  studentId: string
  course: CourseEnrollment
  groupId: string
  lessonNumber: number
  childNumber?: number | undefined
}) {
  const principal = useAuthenticatedPrincipal()
  const navigate = useNavigate()
  const query = useFamilyWorksheetQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    studentId,
    course.course.courseId,
    groupId,
    lessonNumber,
  )
  const mark = (problem: StudentProblemSummary | undefined) =>
    problem ? (
      <Badge variant={problem.status === 'accepted' ? 'success' : 'neutral'}>
        {problem.verdict?.symbol ??
          (problem.status === 'sent' || problem.status === 'checking'
            ? 'На проверке'
            : 'Не начата')}
      </Badge>
    ) : null
  return (
    <PageLayout
      title={`Занятие ${lessonNumber}`}
      width="content"
      actions={
        <label className="flex items-center gap-2 text-small">
          Группа
          <select
            aria-label="Группа листка"
            className="min-h-10 rounded-md border border-input bg-surface px-3"
            value={groupId}
            onChange={(event) => {
              const group = course.allowedGroups.find((item) => item.groupId === event.target.value)
              if (group)
                void navigate({
                  to: '/tasks/$courseCode/$groupCode/$lessonNumber',
                  params: {
                    courseCode: course.course.code,
                    groupCode: group.code,
                    lessonNumber: String(lessonNumber),
                  },
                  search: childNumber === undefined ? {} : { child: childNumber },
                })
            }}
          >
            {course.allowedGroups.map((group) => (
              <option key={group.groupId} value={group.groupId}>
                {group.name}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {query.isPending ? (
        <PageStatePanel state="loading" />
      ) : query.error ? (
        <PageStatePanel
          state={
            query.error instanceof ApiResponseError && query.error.status === 404
              ? 'empty'
              : 'error'
          }
          title="Листок пока недоступен"
          description={
            query.error instanceof ApiResponseError && query.error.status === 404
              ? 'Условие этого занятия для выбранной группы ещё не опубликовано.'
              : 'Не удалось загрузить условия и оценки. Попробуйте ещё раз.'
          }
          actionLabel="Повторить"
          onAction={() => void query.refetch()}
        />
      ) : (
        <SemanticMathDocument
          imageLoading="eager"
          className="vmsh-student-sheet rounded-xl border border-border bg-surface px-4 py-5 sm:px-7 sm:py-6"
          document={query.data.document}
          renderProblemActions={(problem) =>
            mark(
              query.data.problems.problems.find(
                (item) => item.sourceOrdinal === problem.ordinal && !hasSubparts(problem.blocks),
              ),
            )
          }
          renderSubpartActions={(problem, label) =>
            mark(
              query.data.problems.problems.find(
                (item) =>
                  item.sourceOrdinal === problem.ordinal && item.displayNumber.endsWith(label),
              ),
            )
          }
        />
      )}
    </PageLayout>
  )
}

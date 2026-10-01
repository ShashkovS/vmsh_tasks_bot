import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
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
import { ContentUpdateMarker, LessonBlocksLayout } from '@vmsh/product'
import { Badge } from '@vmsh/ui'

function hasSubparts(blocks: WebContentBlock[]): boolean {
  return blocks.some(
    (block) =>
      block.type === 'subpart' ||
      ('blocks' in block && hasSubparts(block.blocks)) ||
      (block.type === 'list' && block.items.some(hasSubparts)),
  )
}

function materialLabel(kind: ContentMaterialKind): string {
  switch (kind) {
    case 'condition':
      return t`Условие`
    case 'hint':
      return t`Подсказка`
    case 'solution':
      return t`Решение`
  }
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
  const materialLabelForKind = materialLabel(kind)
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
      <PageLayout title={t`Задача ${taskId}`} width="reading">
        <PageStatePanel
          description={
            !studentPublicId
              ? t`У аккаунта родителя нет доступного профиля ребёнка.`
              : t`Откройте задачу из опубликованного листка ребёнка.`
          }
          state="empty"
          title={!studentPublicId ? t`Не выбран ребёнок` : t`Не указан опубликованный листок`}
        />
      </PageLayout>
    )
  }
  if (query.isPending) {
    return (
      <PageLayout title={materialLabelForKind} width="reading">
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
      <PageLayout title={materialLabelForKind} width="reading">
        <PageStatePanel
          {...(state === 'error' || state === 'offline'
            ? { actionLabel: t`Повторить`, onAction: () => void query.refetch() }
            : {})}
          {...(state === 'empty'
            ? {
                description: t`Этот материал ещё не опубликован для выбранной группы ребёнка.`,
              }
            : {})}
          description={t`Не удалось загрузить материал. Попробуйте ещё раз.`}
          state={state}
          {...(state === 'empty' ? { title: t`Материал пока закрыт` } : {})}
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
      <PageLayout title={document.title ?? materialLabelForKind} width="reading">
        <PageStatePanel state="empty" title={t`Задача не найдена`} />
      </PageLayout>
    )
  }
  const visibleDocument = selectedProblem
    ? { ...document, introduction: [], problems: [selectedProblem] }
    : document

  return (
    <PageLayout
      eyebrow={materialLabelForKind}
      title={
        selectedProblem
          ? t`Задача ${selectedProblem.taskReference ?? selectedProblem.ordinal}.${selectedProblem.title ? ` «${selectedProblem.title}»` : ''}`
          : (displayTitle ?? document.title ?? materialLabelForKind)
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
      <PageLayout title={t`Листок`} width="content">
        <PageStatePanel state="empty" title={t`Не выбран ребёнок`} />
      </PageLayout>
    )
  }
  if (query.isPending) {
    return (
      <PageLayout title={t`Листок`} width="content">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    return (
      <PageLayout title={t`Листок`} width="content">
        <PageStatePanel
          actionLabel={t`Повторить`}
          onAction={() => void query.refetch()}
          state="error"
          description={t`Не удалось загрузить данные ребёнка. Попробуйте ещё раз.`}
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
      <PageLayout title={t`Листок`} width="content">
        <PageStatePanel
          state="forbidden"
          description={t`Эта группа недоступна выбранному ребёнку.`}
        />
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
            ? t`На проверке`
            : t`Не начата`)}
      </Badge>
    ) : null
  return (
    <PageLayout
      title={t`Занятие ${lessonNumber}`}
      width="content"
      actions={
        <label className="flex items-center gap-2 text-small">
          <Trans>Группа</Trans>
          <select
            aria-label={t`Группа листка`}
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
          title={t`Листок пока недоступен`}
          description={
            query.error instanceof ApiResponseError && query.error.status === 404
              ? t`Условие этого занятия для выбранной группы ещё не опубликовано.`
              : t`Не удалось загрузить условия и оценки. Попробуйте ещё раз.`
          }
          actionLabel={t`Повторить`}
          onAction={() => void query.refetch()}
        />
      ) : (
        <LessonBlocksLayout
          after={query.data.lesson.blocks.after?.document ?? null}
          before={query.data.lesson.blocks.before?.document ?? null}
          idPrefix={`family-${query.data.lesson.groupLessonId}`}
        >
          {query.data.document && query.data.problems ? (
            <SemanticMathDocument
              imageLoading="eager"
              className="vmsh-student-sheet rounded-xl border border-border bg-surface px-4 py-5 sm:px-7 sm:py-6"
              document={query.data.document}
              renderProblemActions={(problem) =>
                mark(
                  query.data.problems?.problems.find(
                    (item) =>
                      item.sourceOrdinal === problem.ordinal && !hasSubparts(problem.blocks),
                  ),
                )
              }
              renderSubpartActions={(problem, label) =>
                mark(
                  query.data.problems?.problems.find(
                    (item) =>
                      item.sourceOrdinal === problem.ordinal && item.displayNumber.endsWith(label),
                  ),
                )
              }
            />
          ) : (
            <p className="py-4 text-muted-foreground">
              <Trans>Задачи ещё не опубликованы.</Trans>
            </p>
          )}
        </LessonBlocksLayout>
      )}
    </PageLayout>
  )
}

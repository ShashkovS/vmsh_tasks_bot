import { useMemo } from 'react'

import {
  createFamilyCourseClient,
  FamilyWrittenThreadNetworkError,
  PageLayout,
  PageStatePanel,
  createFamilyWrittenThreadClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useFamilyChildHomeQuery,
  useFamilyWrittenThreadQuery,
} from '@vmsh/app-shell'
import {
  ContentNetworkError,
  SemanticMathDocument,
  createContentApiClient,
  usePublishedContentReplacement,
  usePublishedContentQuery,
} from '@vmsh/content'
import { ApiResponseError, publicIdSchema, type ContentMaterialKind } from '@vmsh/contracts'
import { ContentUpdateMarker, WrittenReviewHistory } from '@vmsh/product'
import { Button, Card, CardContent } from '@vmsh/ui'

const materialLabels: Record<ContentMaterialKind, string> = {
  condition: 'Условие',
  hint: 'Подсказка',
  solution: 'Решение',
}

function FamilyWrittenThreadView({
  studentId,
  problemId,
}: {
  studentId: string
  problemId: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') throw new Error('Family thread requires a Family principal')
  const client = useMemo(
    () =>
      createFamilyWrittenThreadClient(authentication.client.runtime, {
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
  const query = useFamilyWrittenThreadQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    studentId,
    problemId,
  )

  if (query.isPending) {
    return (
      <p aria-live="polite" className="text-small text-muted-foreground">
        Загружаем отправленное решение и результат проверки…
      </p>
    )
  }
  if (query.error) {
    const offline = query.error instanceof FamilyWrittenThreadNetworkError
    return (
      <Card role="alert">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-5">
          <p className="text-small text-muted-foreground">
            {offline
              ? 'Результат пока недоступен без связи.'
              : 'Не удалось безопасно загрузить результат проверки.'}
          </p>
          <Button onClick={() => void query.refetch()} size="sm" variant="outline">
            Повторить
          </Button>
        </CardContent>
      </Card>
    )
  }
  const thread = query.data.thread
  if (thread === null) return null
  const studentEntries = thread.entries.filter((entry) => entry.authorKind === 'student')

  return (
    <div className="mt-6 space-y-5">
      <section aria-label="Отправленное решение ребёнка" className="space-y-3">
        <h2 className="text-title font-semibold text-foreground">Отправленное решение</h2>
        {studentEntries.map((entry) => (
          <Card key={entry.entryId}>
            <CardContent className="space-y-3 pt-5">
              {entry.text ? <p className="font-reading text-body">{entry.text}</p> : null}
              {entry.attachments.length ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {entry.attachments.map((attachment, index) => (
                    <img
                      alt={`Страница решения ${index + 1}`}
                      className="w-full rounded-md border border-paper-edge bg-paper object-contain"
                      key={attachment.attachmentId}
                      loading="lazy"
                      src={attachment.mediaPath}
                    />
                  ))}
                </div>
              ) : null}
              <time className="block text-caption text-muted-foreground">
                Отправлено {new Date(entry.serverReceivedAt).toLocaleString('ru-RU')}
              </time>
            </CardContent>
          </Card>
        ))}
      </section>
      {thread.reviews.length ? (
        <WrittenReviewHistory entries={thread.entries} reviews={thread.reviews} />
      ) : (
        <p className="text-small text-muted-foreground">Решение ждёт проверки.</p>
      )}
    </div>
  )
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
      title={selectedProblem?.title ?? displayTitle ?? document.title ?? materialLabels[kind]}
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
      {kind === 'condition' &&
      problemOrdinal !== undefined &&
      publicIdSchema.safeParse(taskId).success ? (
        <FamilyWrittenThreadView problemId={taskId} studentId={studentPublicId} />
      ) : null}
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
  const query = useFamilyChildHomeQuery(
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
        />
      </PageLayout>
    )
  }
  const course = query.data.courses.find(
    ({ enrollment }) =>
      enrollment.course.code.toLocaleLowerCase('ru-RU') === courseCode.toLocaleLowerCase('ru-RU'),
  )
  const group = course?.enrollment.allowedGroups.find(
    (candidate) =>
      candidate.code.toLocaleLowerCase('ru-RU') === groupCode.toLocaleLowerCase('ru-RU'),
  )
  const lesson = course?.currentLesson
  if (
    !course ||
    !group ||
    course.enrollment.activeGroupId !== group.groupId ||
    lesson?.lessonNumber !== lessonNumber
  ) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel
          description="Проверьте код курса, группы и номер занятия в ссылке."
          state="empty"
          title="Листок не найден"
        />
      </PageLayout>
    )
  }
  return (
    <FamilyPublishedContentPage
      displayTitle={lesson.title?.trim() || `Занятие ${lesson.lessonNumber}`}
      groupLessonId={lesson.groupLessonId}
      kind="condition"
      requestedStudentPublicId={selectedChild.studentId}
      taskId={`lesson-${lesson.lessonNumber}`}
    />
  )
}

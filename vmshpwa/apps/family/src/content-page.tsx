import { useMemo } from 'react'

import { PageLayout, PageStatePanel, useAuthentication } from '@vmsh/app-shell'
import {
  ContentNetworkError,
  SemanticMathDocument,
  createContentApiClient,
  usePublishedContentReplacement,
  usePublishedContentQuery,
} from '@vmsh/content'
import { ApiResponseError, type ContentMaterialKind } from '@vmsh/contracts'
import { ContentUpdateMarker } from '@vmsh/product'

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
}: {
  taskId: string
  groupLessonId?: string
  kind: ContentMaterialKind
  requestedStudentPublicId?: string
  problemOrdinal?: number
}) {
  const authentication = useAuthentication()
  const principal =
    authentication.state.status === 'authenticated' ||
    authentication.state.status === 'offline-unverified'
      ? authentication.state.principal
      : undefined
  const linkedChildren = principal?.audience === 'family' ? principal.linkedChildren : []
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
      description="Только чтение: сдача и реакции доступны в кабинете ребёнка."
      eyebrow={materialLabels[kind]}
      title={selectedProblem?.title ?? document.title ?? `Задача ${taskId}`}
      width="reading"
    >
      <ContentUpdateMarker visible={contentWasReplaced} />
      <SemanticMathDocument document={visibleDocument} />
    </PageLayout>
  )
}

import { useMemo, type ReactNode } from 'react'

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

/**
 * Real Student content boundary for Phase 2. The route supplies validated
 * group-lesson/material search state; no protected prototype is used when the
 * context is incomplete. See `dev/development-plan/06-phase-2-content.md`.
 */
export function StudentPublishedContentPage({
  taskId,
  groupLessonId,
  kind,
  problemOrdinal,
  afterDocument,
}: {
  taskId: string
  groupLessonId?: string
  kind: ContentMaterialKind
  problemOrdinal?: number
  afterDocument?: ReactNode
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
  const query = usePublishedContentQuery(
    client,
    { groupLessonId: groupLessonId ?? 'missing', kind },
    { enabled: groupLessonId !== undefined },
  )
  const contentWasReplaced = usePublishedContentReplacement(
    groupLessonId ? `student:${groupLessonId}:${kind}` : undefined,
    query.data?.revisionId,
  )

  if (!groupLessonId) {
    return (
      <PageLayout title={`Задача ${taskId}`} width="reading">
        <PageStatePanel
          description="Откройте задачу из опубликованного листка: ссылка должна содержать занятие и вид материала."
          state="empty"
          title="Не указан опубликованный листок"
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
            ? { description: 'Этот материал ещё не опубликован для вашей группы.' }
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
        <PageStatePanel
          description="В опубликованной версии листка такой задачи нет. Обновите ссылку из списка задач."
          state="empty"
          title="Задача не найдена"
        />
      </PageLayout>
    )
  }
  const visibleDocument = selectedProblem
    ? { ...document, introduction: [], problems: [selectedProblem] }
    : document

  return (
    <PageLayout
      description={`Опубликовано ${new Date(query.data.publishedAt).toLocaleString('ru-RU')}`}
      eyebrow={materialLabels[kind]}
      title={selectedProblem?.title ?? document.title ?? `Задача ${taskId}`}
      width="reading"
    >
      <ContentUpdateMarker visible={contentWasReplaced} />
      <SemanticMathDocument document={visibleDocument} />
      {afterDocument}
    </PageLayout>
  )
}

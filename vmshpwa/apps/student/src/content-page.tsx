import { useMemo, type ReactNode } from 'react'

import {
  PageLayout,
  PageStatePanel,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ContentNetworkError,
  SemanticMathDocument,
  createContentApiClient,
  usePublishedContentReplacement,
  usePublishedContentQuery,
} from '@vmsh/content'
import { ApiResponseError, type ContentMaterialKind, type WebContentProblem } from '@vmsh/contracts'
import { useOfflineDatabase } from '@vmsh/offline'
import { ContentUpdateMarker } from '@vmsh/product'

import { createOfflineStudentPublishedContentClient } from './offline-student-data'

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
  displayTitle,
  afterDocument,
  beforeDocument,
  containerClassName,
  documentClassName,
  pageWidth,
  renderAfterProblem,
  renderAfterSubpart,
  renderProblemActions,
  renderSubpartActions,
  hidePageHeading = false,
}: {
  taskId: string
  groupLessonId?: string
  kind: ContentMaterialKind
  problemOrdinal?: number
  displayTitle?: string
  afterDocument?: ReactNode
  beforeDocument?: ReactNode
  containerClassName?: string
  documentClassName?: string
  pageWidth?: 'reading' | 'content' | 'wide'
  renderAfterProblem?: (problem: WebContentProblem) => ReactNode
  renderAfterSubpart?: (problem: WebContentProblem, label: string) => ReactNode
  renderProblemActions?: (problem: WebContentProblem) => ReactNode
  renderSubpartActions?: (problem: WebContentProblem, label: string) => ReactNode
  hidePageHeading?: boolean
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') {
    throw new Error('Student content requires a Student principal')
  }
  const database = useOfflineDatabase()
  const client = useMemo(() => {
    const online = createContentApiClient(authentication.client.runtime, {
      refreshSession: async () => {
        try {
          return await authentication.refresh()
        } catch (error) {
          authentication.handleApiError(error)
          throw error
        }
      },
    })
    return createOfflineStudentPublishedContentClient(online, database, principal.accountId)
  }, [authentication, database, principal.accountId])
  const query = usePublishedContentQuery(
    client,
    { audience: 'student', accountId: principal.accountId },
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
    ? {
        ...document,
        introduction: [],
        problems: [{ ...selectedProblem, trailingBlocks: [] }],
      }
    : document
  const visibleTitle =
    displayTitle ||
    (selectedProblem
      ? `Задача ${selectedProblem.taskReference ?? selectedProblem.ordinal}.${selectedProblem.title ? ` «${selectedProblem.title}»` : ''}`
      : document.title || materialLabels[kind])

  const renderedContent = (
    <div data-print-lesson>
      <div data-print-hide>
        <ContentUpdateMarker visible={contentWasReplaced} />
        {beforeDocument}
      </div>
      <SemanticMathDocument
        {...(documentClassName ? { className: documentClassName } : {})}
        document={visibleDocument}
        imageLoading="eager"
        {...(renderAfterProblem ? { renderAfterProblem } : {})}
        {...(renderAfterSubpart ? { renderAfterSubpart } : {})}
        {...(renderProblemActions ? { renderProblemActions } : {})}
        {...(renderSubpartActions ? { renderSubpartActions } : {})}
      />
      <div data-print-hide>{afterDocument}</div>
    </div>
  )

  if (hidePageHeading) {
    const widthClass =
      pageWidth === 'wide'
        ? 'max-w-[112rem]'
        : pageWidth === 'content'
          ? 'max-w-[96rem]'
          : 'max-w-[90ch]'
    return (
      <main className={containerClassName ?? `mx-auto w-full px-3 py-4 sm:px-5 ${widthClass}`}>
        {renderedContent}
      </main>
    )
  }

  return (
    <PageLayout
      description={`Опубликовано ${new Date(query.data.publishedAt).toLocaleString('ru-RU')}`}
      eyebrow={materialLabels[kind]}
      title={visibleTitle}
      width={pageWidth ?? 'reading'}
    >
      {renderedContent}
    </PageLayout>
  )
}

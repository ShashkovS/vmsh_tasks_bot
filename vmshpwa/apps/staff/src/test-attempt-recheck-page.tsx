import { t } from '@lingui/core/macro'
import { useMemo } from 'react'

import {
  PageLayout,
  PageStatePanel,
  TestAttemptRecheckNetworkError,
  TestAttemptRecheckProtocolError,
  createTestAttemptRecheckClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useTestAttemptRecheckMutation,
  useTestAttemptRecheckPreviewQuery,
} from '@vmsh/app-shell'
import { ApiResponseError } from '@vmsh/contracts'
import { TestAttemptRecheckPanel } from '@vmsh/product'

/**
 * Production Staff composition for current-state test-answer repair.
 * The server enforces checker.manage and the product panel only displays the
 * preview-bound aggregate action. See
 * `dev/design-system/05-pages-and-flows.md` and `TestAttemptRecheckPanel`.
 */
export function StaffTestAttemptRecheckPage({ problemId }: { problemId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () =>
      createTestAttemptRecheckClient(authentication.client.runtime, {
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
  const preview = useTestAttemptRecheckPreviewQuery(client, principal, problemId)
  const recheck = useTestAttemptRecheckMutation(client, principal, problemId)

  const apply = async () => {
    if (!preview.data || recheck.isPending) return
    if (
      !window.confirm(
        t`Перепроверить все ${preview.data.pendingAttempts} ответов задачи ${preview.data.problem.displayNumber}? Исходные ответы и время отправки сохранятся.`,
      )
    ) {
      return
    }
    recheck.reset()
    try {
      await recheck.mutateAsync({
        schemaVersion: 1,
        problemRevision: preview.data.problemRevision,
      })
    } catch (error) {
      authentication.handleApiError(error)
      if (error instanceof ApiResponseError && error.status === 409) {
        await preview.refetch()
      }
    }
  }

  return (
    <PageLayout
      description={t`Исправление конфигурации не меняет исходные ответы: их текущий вердикт пересчитывается по новой настройке.`}
      eyebrow={t`Администрирование тестовой задачи`}
      title={
        preview.data
          ? t`Задача ${preview.data.problem.displayNumber}. ${preview.data.problem.title}`
          : t`Задача ${problemId}`
      }
      width="wide"
    >
      {preview.isPending ? (
        <TestAttemptRecheckPanel loading />
      ) : preview.error ? (
        <PageStatePanel
          actionLabel={t`Повторить`}
          description={describeRecheckError(preview.error)}
          onAction={() => void preview.refetch()}
          state={
            preview.error instanceof ApiResponseError && preview.error.status === 403
              ? 'forbidden'
              : 'error'
          }
          {...(preview.error instanceof ApiResponseError && preview.error.status === 404
            ? { title: t`Задача не найдена` }
            : {})}
        />
      ) : preview.data ? (
        <TestAttemptRecheckPanel
          applying={recheck.isPending}
          onApply={() => void apply()}
          onRetry={() => {
            recheck.reset()
            void preview.refetch()
          }}
          pendingAttempts={preview.data.pendingAttempts}
          studentCount={preview.data.students}
          updatesRequired={preview.data.updatesRequired}
          verdictChanges={preview.data.verdictChanges}
          becameCorrect={preview.data.becameCorrect}
          becameWrong={preview.data.becameWrong}
          formatChanges={preview.data.formatChanges}
          invalidFormat={preview.data.invalidFormat}
          pendingConfiguration={preview.data.pendingConfiguration}
          checkerFailed={preview.data.checkerFailed}
          messageChanges={preview.data.messageChanges}
          problem={preview.data.problem}
          problemRevision={preview.data.problemRevision}
          {...(recheck.error ? { error: describeRecheckError(recheck.error) } : {})}
          {...(recheck.data ? { result: recheck.data } : {})}
        />
      ) : null}
    </PageLayout>
  )
}

function describeRecheckError(error: unknown): string {
  if (error instanceof ApiResponseError && error.status === 409) {
    return t`Опубликована новая версия задачи. Данные обновлены; проверьте действие ещё раз.`
  }
  if (error instanceof ApiResponseError) {
    return t`${error.message} Код обращения: ${error.requestId}.`
  }
  if (error instanceof TestAttemptRecheckNetworkError) {
    return t`Нет связи с сервером. Проверьте подключение и повторите действие.`
  }
  if (error instanceof TestAttemptRecheckProtocolError) {
    return t`Сервер вернул неожиданный ответ. Обновите страницу и повторите действие.`
  }
  return t`Не удалось перепроверить ответы. Обновите данные и повторите действие.`
}

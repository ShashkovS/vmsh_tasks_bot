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
 * Production Staff composition for Phase 4's pending-configuration repair.
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
      description="Исправление конфигурации не меняет исходные ответы: система добавляет только результат проверки."
      eyebrow="Администрирование тестовой задачи"
      title={`Задача ${problemId}`}
      width="wide"
    >
      {preview.isPending ? (
        <TestAttemptRecheckPanel loading />
      ) : preview.error ? (
        <PageStatePanel
          actionLabel="Повторить"
          description={describeRecheckError(preview.error)}
          onAction={() => void preview.refetch()}
          state={
            preview.error instanceof ApiResponseError && preview.error.status === 403
              ? 'forbidden'
              : 'error'
          }
          {...(preview.error instanceof ApiResponseError && preview.error.status === 404
            ? { title: 'Задача не найдена' }
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
    return 'Опубликована новая версия задачи. Данные обновлены; проверьте действие ещё раз.'
  }
  if (error instanceof ApiResponseError) {
    return `${error.message} Код обращения: ${error.requestId}.`
  }
  if (error instanceof TestAttemptRecheckNetworkError) {
    return 'Нет связи с сервером. Проверьте подключение и повторите действие.'
  }
  if (error instanceof TestAttemptRecheckProtocolError) {
    return 'Сервер вернул неожиданный ответ. Обновите страницу и повторите действие.'
  }
  return 'Не удалось перепроверить ответы. Обновите данные и повторите действие.'
}

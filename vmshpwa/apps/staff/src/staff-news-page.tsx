import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createNewsModerationClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useNewsModerationQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  newsQueryKeys,
  type StaffNewsItem,
  type StaffNewsVisibilityFilter,
} from '@vmsh/contracts'
import { NewsModerationList } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Label } from '@vmsh/ui'

type Command = { item: StaffNewsItem; state: 'visible' | 'manual_hidden' }

export function StaffNewsPage({
  state,
  onStateChange,
}: {
  state: StaffNewsVisibilityFilter
  onStateChange: (state: StaffNewsVisibilityFilter) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('News moderation requires Staff auth')
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const client = useMemo(
    () =>
      createNewsModerationClient(authentication.client.runtime, {
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
  const query = useNewsModerationQuery(client, scope, state)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: ({ item, state: targetState }: Command) =>
      client.changeVisibility(item.postId, item.version, {
        schemaVersion: 1,
        state: targetState,
        reason: null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: newsQueryKeys.moderation(scope, state) })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  let content
  if (query.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (query.error) {
    content = (
      <PageStatePanel
        actionLabel="Повторить"
        onAction={() => void query.refetch()}
        state={
          query.error instanceof ApiResponseError && query.error.status === 403
            ? 'forbidden'
            : 'error'
        }
      />
    )
  } else if (query.data.items.length === 0) {
    content = <PageStatePanel state="empty" />
  } else {
    content = (
      <NewsModerationList
        items={query.data.items}
        onHide={(item) => mutation.mutate({ item, state: 'manual_hidden' })}
        onRestore={(item) => mutation.mutate({ item, state: 'visible' })}
        pendingPostId={mutation.isPending ? mutation.variables.item.postId : null}
      />
    )
  }

  return (
    <PageLayout
      actions={
        <Label className="grid gap-1 text-caption">
          Состояние
          <select
            className="min-h-9 rounded-md border border-input bg-surface px-3 text-small"
            onChange={(event) => onStateChange(event.target.value as StaffNewsVisibilityFilter)}
            value={state}
          >
            <option value="all">Все</option>
            <option value="visible">В ленте</option>
            <option value="manual_hidden">Скрыты в PWA</option>
            <option value="source_deleted">Удалены в Telegram</option>
          </select>
        </Label>
      }
      description="Локальные копии Telegram-постов. Скрытие влияет только на PWA и не меняет сообщение в Telegram."
      title="Новости"
      width="wide"
    >
      <div className="space-y-3">
        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Изменение не сохранено</AlertTitle>
              <AlertDescription>
                {mutation.error instanceof ApiResponseError
                  ? mutation.error.message
                  : 'Проверьте соединение и повторите попытку.'}
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {content}
      </div>
    </PageLayout>
  )
}

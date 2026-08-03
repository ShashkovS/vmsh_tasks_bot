import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  createNewsModerationClient,
  useAdminCourseCatalogQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
  useNewsModerationQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  newsQueryKeys,
  type CreateLocalNewsRequest,
  type StaffNewsItem,
  type StaffNewsVisibilityFilter,
} from '@vmsh/contracts'
import { NewsModerationList } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Label,
  Textarea,
} from '@vmsh/ui'

import {
  EMPTY_LOCAL_NEWS_DRAFT,
  clearLocalNewsDraft,
  loadLocalNewsDraft,
  moscowDateTime,
  saveLocalNewsDraft,
} from './local-news-draft'
import { StaffLocalNewsComposer } from './staff-local-news-composer'

type Command =
  | { kind: 'visibility'; item: StaffNewsItem; state: 'visible' | 'manual_hidden' }
  | { kind: 'source'; item: StaffNewsItem; state: 'deleted' | 'present'; reason: string }
  | { kind: 'local'; request: CreateLocalNewsRequest }

type SourceCommand = { item: StaffNewsItem; state: 'deleted' | 'present' }

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
  const catalogClient = useMemo(
    () =>
      createAdminCourseClient(authentication.client.runtime, {
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
  const [sourceCommand, setSourceCommand] = useState<SourceCommand | null>(null)
  const [sourceReason, setSourceReason] = useState('')
  const [localOpen, setLocalOpen] = useState(false)
  const draftKey = `${authentication.client.runtime.instance}:staff:${principal.accountId}:local-news-draft:v1`
  const [localDraft, setLocalDraft] = useState(() =>
    loadLocalNewsDraft(globalThis.localStorage, draftKey),
  )
  const catalog = useAdminCourseCatalogQuery(catalogClient, scope, undefined, localOpen)
  useEffect(() => {
    if (localDraft.owner === '' && localDraft.text === '' && localDraft.publishedLocal === '') {
      clearLocalNewsDraft(globalThis.localStorage, draftKey)
    } else {
      saveLocalNewsDraft(globalThis.localStorage, draftKey, localDraft)
    }
  }, [draftKey, localDraft])
  const mutation = useMutation({
    mutationFn: (command: Command) =>
      command.kind === 'local'
        ? client.createLocal(command.request)
        : command.kind === 'visibility'
          ? client.changeVisibility(command.item.postId, command.item.version, {
              schemaVersion: 1,
              state: command.state,
              reason: null,
            })
          : client.reconcileSource(command.item.postId, command.item.version, {
              schemaVersion: 1,
              sourceState: command.state,
              reason: command.reason,
            }),
    onSuccess: async (_result, command) => {
      setSourceCommand(null)
      setSourceReason('')
      if (command.kind === 'local') {
        clearLocalNewsDraft(globalThis.localStorage, draftKey)
        setLocalDraft(EMPTY_LOCAL_NEWS_DRAFT)
        setLocalOpen(false)
      }
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
        onHide={(item) => mutation.mutate({ kind: 'visibility', item, state: 'manual_hidden' })}
        onMarkSourceDeleted={(item) => setSourceCommand({ item, state: 'deleted' })}
        onMarkSourcePresent={(item) => setSourceCommand({ item, state: 'present' })}
        onRestore={(item) => mutation.mutate({ kind: 'visibility', item, state: 'visible' })}
        pendingPostId={
          mutation.isPending && mutation.variables.kind !== 'local'
            ? mutation.variables.item.postId
            : null
        }
      />
    )
  }

  return (
    <PageLayout
      actions={
        <div className="flex flex-wrap items-end gap-2">
          <Button onClick={() => setLocalOpen(true)} type="button">
            Создать публикацию
          </Button>
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
        </div>
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
        <Dialog
          onOpenChange={(open) => {
            if (!mutation.isPending) setLocalOpen(open)
          }}
          open={localOpen}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Новая публикация в PWA</DialogTitle>
              <DialogDescription>
                Публикация появится в ленте выбранного курса или группы в указанное время. Telegram
                не изменяется.
              </DialogDescription>
            </DialogHeader>
            {catalog.isPending ? <PageStatePanel state="loading" /> : null}
            {catalog.error ? (
              <Alert role="alert" tone="danger">
                <AlertContent>
                  <AlertTitle>Не удалось загрузить курсы</AlertTitle>
                  <AlertDescription>Закройте окно и повторите попытку.</AlertDescription>
                </AlertContent>
              </Alert>
            ) : null}
            {catalog.data ? (
              <StaffLocalNewsComposer
                courses={catalog.data.courses}
                draft={localDraft}
                onChange={setLocalDraft}
                onSubmit={() => {
                  const separator = localDraft.owner.indexOf(':')
                  const publishedAt = moscowDateTime(localDraft.publishedLocal)
                  if (separator < 1 || publishedAt === null) return
                  mutation.mutate({
                    kind: 'local',
                    request: {
                      schemaVersion: 1,
                      ownerType: localDraft.owner.slice(0, separator) as 'course' | 'group',
                      ownerId: localDraft.owner.slice(separator + 1),
                      text: localDraft.text,
                      publishedAt,
                    },
                  })
                }}
                pending={mutation.isPending && mutation.variables.kind === 'local'}
              />
            ) : null}
          </DialogContent>
        </Dialog>
        <Dialog
          onOpenChange={(open) => {
            if (!open && !mutation.isPending) {
              setSourceCommand(null)
              setSourceReason('')
            }
          }}
          open={sourceCommand !== null}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {sourceCommand?.state === 'deleted'
                  ? 'Пост удалён в Telegram?'
                  : 'Пост снова доступен?'}
              </DialogTitle>
              <DialogDescription>
                Эта ручная сверка меняет PWA-ленту и сохраняется в журнале. Само сообщение в
                Telegram не изменяется.
              </DialogDescription>
            </DialogHeader>
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (sourceCommand === null || sourceReason.trim() === '') return
                mutation.mutate({
                  kind: 'source',
                  item: sourceCommand.item,
                  state: sourceCommand.state,
                  reason: sourceReason.trim(),
                })
              }}
            >
              <Label className="grid gap-1.5" htmlFor="news-source-reason">
                Краткая причина
                <Textarea
                  id="news-source-reason"
                  maxLength={500}
                  onChange={(event) => setSourceReason(event.target.value)}
                  placeholder="Например: проверено в канале, пост отсутствует"
                  rows={3}
                  value={sourceReason}
                />
              </Label>
              <DialogFooter>
                <Button
                  disabled={mutation.isPending}
                  onClick={() => {
                    setSourceCommand(null)
                    setSourceReason('')
                  }}
                  type="button"
                  variant="outline"
                >
                  Отмена
                </Button>
                <Button disabled={mutation.isPending || sourceReason.trim() === ''} type="submit">
                  Сохранить сверку
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </PageLayout>
  )
}

import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createAdminCourseClient,
  createNewsModerationClient,
  createStaffRichMediaClient,
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
  type UpdateLocalNewsRequest,
} from '@vmsh/contracts'
import { NewsModerationList } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
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
  toMoscowLocalDateTime,
} from './local-news-draft'
import { StaffLocalNewsComposer } from './staff-local-news-composer'

type Command =
  | { kind: 'visibility'; item: StaffNewsItem; state: 'visible' | 'manual_hidden' }
  | { kind: 'source'; item: StaffNewsItem; state: 'deleted' | 'present'; reason: string }
  | { kind: 'local'; request: CreateLocalNewsRequest }
  | { kind: 'edit-local'; item: StaffNewsItem; request: UpdateLocalNewsRequest }

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
  const richMediaClient = useMemo(
    () =>
      createStaffRichMediaClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const query = useNewsModerationQuery(client, scope, state)
  const queryClient = useQueryClient()
  const [sourceCommand, setSourceCommand] = useState<SourceCommand | null>(null)
  const [sourceReason, setSourceReason] = useState('')
  const [editingItem, setEditingItem] = useState<StaffNewsItem | null>(null)
  const [editDraft, setEditDraft] = useState(EMPTY_LOCAL_NEWS_DRAFT)
  const draftKey = `${authentication.client.runtime.instance}:staff:${principal.accountId}:local-news-draft:v1`
  const [localDraft, setLocalDraft] = useState(() =>
    loadLocalNewsDraft(globalThis.localStorage, draftKey),
  )
  const catalog = useAdminCourseCatalogQuery(catalogClient, scope, undefined, true)
  const editDraftKey =
    editingItem === null
      ? null
      : `${authentication.client.runtime.instance}:staff:${principal.accountId}:local-news-edit:${editingItem.postId}:v${editingItem.version}`
  useEffect(() => {
    if (localDraft.text === '' && localDraft.publishedLocal === '') {
      clearLocalNewsDraft(globalThis.localStorage, draftKey)
    } else {
      saveLocalNewsDraft(globalThis.localStorage, draftKey, localDraft)
    }
  }, [draftKey, localDraft])
  useEffect(() => {
    if (editDraftKey !== null) {
      saveLocalNewsDraft(globalThis.localStorage, editDraftKey, editDraft)
    }
  }, [editDraft, editDraftKey])
  const mutation = useMutation({
    mutationFn: (command: Command) => {
      if (command.kind === 'local') return client.createLocal(command.request)
      if (command.kind === 'edit-local') {
        return client.updateLocal(command.item.postId, command.item.version, command.request)
      }
      if (command.kind === 'visibility') {
        return client.changeVisibility(command.item.postId, command.item.version, {
          schemaVersion: 1,
          state: command.state,
          reason: null,
        })
      }
      return client.reconcileSource(command.item.postId, command.item.version, {
        schemaVersion: 1,
        sourceState: command.state,
        reason: command.reason,
      })
    },
    onSuccess: async (_result, command) => {
      setSourceCommand(null)
      setSourceReason('')
      if (command.kind === 'local') {
        clearLocalNewsDraft(globalThis.localStorage, draftKey)
        setLocalDraft(EMPTY_LOCAL_NEWS_DRAFT)
      }
      if (command.kind === 'edit-local') {
        clearLocalNewsDraft(
          globalThis.localStorage,
          `${authentication.client.runtime.instance}:staff:${principal.accountId}:local-news-edit:${command.item.postId}:v${command.item.version}`,
        )
        setEditingItem(null)
        setEditDraft(EMPTY_LOCAL_NEWS_DRAFT)
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
        actionLabel={t`Повторить`}
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
        onEdit={(item) => {
          const key = `${authentication.client.runtime.instance}:staff:${principal.accountId}:local-news-edit:${item.postId}:v${item.version}`
          const initial = {
            courseId: item.courseId,
            groupId: item.groupId ?? '',
            audience: item.audience,
            attendanceMode: item.attendanceMode,
            text: item.markdown ?? item.editableText ?? '',
            publishedLocal: toMoscowLocalDateTime(item.publishedAt) ?? '',
          }
          const saved = loadLocalNewsDraft(globalThis.localStorage, key, initial)
          const hasSavedDraft =
            saved.courseId !== '' ||
            saved.groupId !== '' ||
            saved.text !== '' ||
            saved.publishedLocal !== ''
          const restored = !hasSavedDraft
            ? initial
            : {
                ...saved,
                courseId: saved.courseId || initial.courseId,
                groupId: saved.groupId || initial.groupId,
              }
          // Published news keeps its original ordering and notification moment.
          // See docs/local-scheduled-news.md and the matching HTTP integration test.
          setEditDraft(
            item.isScheduled
              ? restored
              : {
                  ...restored,
                  courseId: initial.courseId,
                  groupId: initial.groupId,
                  audience: initial.audience,
                  attendanceMode: initial.attendanceMode,
                  publishedLocal: initial.publishedLocal,
                },
          )
          setEditingItem(item)
        }}
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
          <Label className="grid gap-1 text-caption">
            <Trans>Состояние</Trans>
            <select
              className="min-h-9 rounded-md border border-input bg-surface px-3 text-small"
              onChange={(event) => onStateChange(event.target.value as StaffNewsVisibilityFilter)}
              value={state}
            >
              <option value="all">
                <Trans>Все</Trans>
              </option>
              <option value="visible">
                <Trans>В ленте</Trans>
              </option>
              <option value="manual_hidden">
                <Trans>Скрыты в PWA</Trans>
              </option>
              <option value="source_deleted">
                <Trans>Удалены в Telegram</Trans>
              </option>
            </select>
          </Label>
        </div>
      }
      description={t`Локальные копии Telegram-постов. Скрытие влияет только на PWA и не меняет сообщение в Telegram.`}
      title={t`Новости`}
      width="wide"
    >
      <div className="space-y-6">
        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>
                <Trans>Изменение не сохранено</Trans>
              </AlertTitle>
              <AlertDescription>
                {mutation.error instanceof ApiResponseError
                  ? mutation.error.message
                  : t`Проверьте соединение и повторите попытку.`}
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <PageSection
          description={t`Публикация появится в ленте выбранного курса или группы в указанное время. Telegram не изменяется.`}
          title={t`Новая публикация в PWA`}
        >
          {catalog.isPending ? <PageStatePanel state="loading" /> : null}
          {catalog.error ? (
            <Alert role="alert" tone="danger">
              <AlertContent>
                <AlertTitle>
                  <Trans>Не удалось загрузить курсы</Trans>
                </AlertTitle>
                <AlertDescription>
                  <Trans>Обновите страницу и повторите попытку.</Trans>
                </AlertDescription>
              </AlertContent>
            </Alert>
          ) : null}
          {catalog.data ? (
            <Card>
              <CardContent className="pt-4">
                <StaffLocalNewsComposer
                  courses={catalog.data.courses}
                  draft={localDraft}
                  onChange={setLocalDraft}
                  onImageUpload={(image) => richMediaClient.uploadImage(image)}
                  onFileUpload={(file) => richMediaClient.uploadFile(file)}
                  onSubmit={(document, courseId) => {
                    const publishedAt = moscowDateTime(localDraft.publishedLocal)
                    if (publishedAt === null) return
                    mutation.mutate({
                      kind: 'local',
                      request: {
                        schemaVersion: 3,
                        courseId,
                        groupId: localDraft.groupId || null,
                        audience: localDraft.audience,
                        attendanceMode: localDraft.attendanceMode,
                        markdown: localDraft.text,
                        document,
                        publishedAt,
                      },
                    })
                  }}
                  pending={mutation.isPending && mutation.variables.kind === 'local'}
                />
              </CardContent>
            </Card>
          ) : null}
        </PageSection>
        <PageSection title={t`Новости`}>{content}</PageSection>
        <Dialog
          onOpenChange={(open) => {
            if (!open && !mutation.isPending) setEditingItem(null)
          }}
          open={editingItem !== null}
        >
          <DialogContent className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingItem?.isScheduled
                  ? t`Изменить запланированную публикацию`
                  : t`Исправить опубликованную новость`}
              </DialogTitle>
              <DialogDescription>
                {editingItem?.isScheduled
                  ? t`Текст и время можно изменить, пока публикация ещё не появилась в ленте. Получатели и Telegram не меняются.`
                  : t`Исправление появится в ленте с пометкой «Обновлено». Повторное уведомление не отправится; время и получатели не меняются.`}
              </DialogDescription>
            </DialogHeader>
            {catalog.isPending ? <PageStatePanel state="loading" /> : null}
            {catalog.isError ? (
              <PageStatePanel
                description={t`Обновите данные и попробуйте открыть редактор ещё раз.`}
                state="error"
                title={t`Не удалось загрузить список получателей`}
              />
            ) : null}
            {catalog.data && editingItem ? (
              <StaffLocalNewsComposer
                courses={catalog.data.courses}
                draft={editDraft}
                onChange={setEditDraft}
                onImageUpload={(image) => richMediaClient.uploadImage(image)}
                onFileUpload={(file) => richMediaClient.uploadFile(file)}
                onSubmit={(document, courseId) => {
                  if (editingItem.isScheduled) {
                    const publishedAt = moscowDateTime(editDraft.publishedLocal)
                    if (publishedAt === null) return
                    mutation.mutate({
                      kind: 'edit-local',
                      item: editingItem,
                      request: {
                        schemaVersion: 3,
                        courseId,
                        groupId: editDraft.groupId || null,
                        audience: editDraft.audience,
                        attendanceMode: editDraft.attendanceMode,
                        markdown: editDraft.text,
                        document,
                        publishedAt,
                      },
                    })
                    return
                  }
                  mutation.mutate({
                    kind: 'edit-local',
                    item: editingItem,
                    request: { schemaVersion: 2, markdown: editDraft.text, document },
                  })
                }}
                pending={mutation.isPending && mutation.variables.kind === 'edit-local'}
                publishedAtDisabled={!editingItem.isScheduled}
                submitLabel={t`Сохранить изменения`}
                targetDisabled={!editingItem.isScheduled}
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
                  ? t`Пост удалён в Telegram?`
                  : t`Пост снова доступен?`}
              </DialogTitle>
              <DialogDescription>
                <Trans>
                  Эта ручная сверка меняет PWA-ленту и сохраняется в журнале. Само сообщение в
                  Telegram не изменяется.
                </Trans>
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
                <Trans>Краткая причина</Trans>
                <Textarea
                  id="news-source-reason"
                  maxLength={500}
                  onChange={(event) => setSourceReason(event.target.value)}
                  placeholder={t`Например: проверено в канале, пост отсутствует`}
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
                  <Trans>Отмена</Trans>
                </Button>
                <Button disabled={mutation.isPending || sourceReason.trim() === ''} type="submit">
                  <Trans>Сохранить сверку</Trans>
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </PageLayout>
  )
}

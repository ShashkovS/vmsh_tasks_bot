import { Link } from '@tanstack/react-router'
import { useMemo } from 'react'

import {
  PageLayout,
  PageStatePanel,
  SupportNetworkError,
  createSupportClient,
  useAppendSupportEntryMutation,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffSupportThreadsInfiniteQuery,
  useSupportThreadQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type StaffSupportListQuery,
  type SupportEntry,
  type SupportThreadSummary,
} from '@vmsh/contracts'
import { useSupportDraftEditor, type SupportDraftDescriptor } from '@vmsh/offline'
import { FeedbackThread, SupportComposer, type ThreadMessageView } from '@vmsh/product'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, buttonVariants } from '@vmsh/ui'

type StaffInboxFilters = Omit<StaffSupportListQuery, 'cursor'>

/** Dense live Staff questions inbox; see Phase 6 Questions/SOS. */
export function StaffSupportInboxPage({ filters }: { filters: StaffInboxFilters }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Staff questions require Staff auth')
  const client = useMemo(
    () =>
      createSupportClient(authentication.client.runtime, {
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
  const query = useStaffSupportThreadsInfiniteQuery(client, principal, filters)
  const items = query.data?.pages.flatMap((page) => page.items) ?? []

  let content
  if (query.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (query.error) {
    content = (
      <PageStatePanel
        {...(supportErrorState(query.error) === 'error' ||
        supportErrorState(query.error) === 'offline'
          ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
          : {})}
        description={describeSupportError(query.error)}
        state={supportErrorState(query.error)}
      />
    )
  } else if (items.length === 0) {
    content = (
      <PageStatePanel
        description="Для выбранного фильтра нет приватных вопросов."
        state="empty"
        title={filters.state === 'awaiting_staff' ? 'Нет вопросов без ответа' : 'Ничего не найдено'}
      />
    )
  } else {
    content = (
      <div className="space-y-3">
        <ol className="grid gap-2 lg:grid-cols-2" aria-label="Вопросы школьников">
          {items.map((item) => (
            <StaffSupportSummary item={item} key={item.threadId} />
          ))}
        </ol>
        {query.hasNextPage ? (
          <Button
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
            size="sm"
            variant="outline"
          >
            {query.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё'}
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <PageLayout
      description="Общие вопросы и вопросы к задачам. Диалог не закрепляется за одним преподавателем."
      eyebrow="Приватные диалоги"
      title="Вопросы школьников"
      width="wide"
    >
      <div className="mb-4 flex flex-wrap gap-1" aria-label="Состояние вопроса">
        {(
          [
            ['awaiting_staff', 'Нужен ответ'],
            ['awaiting_student', 'Ждём школьника'],
            ['all', 'Все'],
          ] as const
        ).map(([state, label]) => (
          <Link
            className={buttonVariants({
              size: 'sm',
              variant: filters.state === state ? 'secondary' : 'ghost',
            })}
            key={state}
            search={(previous) => ({ ...previous, state })}
            to="/questions"
          >
            {label}
          </Link>
        ))}
      </div>
      {content}
    </PageLayout>
  )
}

function StaffSupportSummary({ item }: { item: SupportThreadSummary }) {
  return (
    <li>
      <Link
        className="block rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        params={{ threadId: item.threadId }}
        to="/questions/$threadId"
      >
        <Card className="h-full transition-colors hover:bg-surface-subtle" size="sm">
          <CardHeader>
            <CardTitle className="flex min-w-0 flex-wrap items-center gap-2">
              <span>{item.student.displayName}</span>
              <Badge variant={item.replyState === 'awaiting_staff' ? 'warning' : 'neutral'}>
                {item.replyState === 'awaiting_staff' ? 'Нужен ответ' : 'Ответ отправлен'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="font-medium text-foreground">
              {item.context.problemTitle ?? 'Общий вопрос по занятию'}
            </p>
            <p className="text-caption text-muted-foreground">{supportContext(item)}</p>
            <p className="line-clamp-2 text-small text-foreground">
              {item.latestEntry.textExcerpt ?? 'Вложение'}
            </p>
            <p className="text-caption text-muted-foreground">
              {formatSupportTime(item.latestEntry.receivedAt)} · сообщений: {item.entryCount}
            </p>
          </CardContent>
        </Card>
      </Link>
    </li>
  )
}

export function StaffSupportThreadPage({ threadId }: { threadId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Staff questions require Staff auth')
  const client = useMemo(
    () =>
      createSupportClient(authentication.client.runtime, {
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
  const query = useSupportThreadQuery(client, principal, threadId)
  const mutation = useAppendSupportEntryMutation(client, principal, threadId)
  const descriptor = useMemo<SupportDraftDescriptor>(
    () => ({
      ownerAccountId: principal.accountId,
      target: { kind: 'existing_thread', threadId },
    }),
    [principal.accountId, threadId],
  )
  const editor = useSupportDraftEditor(
    { audience: 'staff', instance: authentication.client.runtime.instance },
    descriptor,
  )

  if (query.isPending) {
    return (
      <PageLayout title="Вопрос школьника" width="content">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    return (
      <PageLayout title="Вопрос школьника" width="content">
        <PageStatePanel
          {...(supportErrorState(query.error) === 'error' ||
          supportErrorState(query.error) === 'offline'
            ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
            : {})}
          description={describeSupportError(query.error)}
          state={supportErrorState(query.error)}
        />
      </PageLayout>
    )
  }

  const thread = query.data.thread
  const submit = async () => {
    mutation.reset()
    try {
      await mutation.mutateAsync({
        schemaVersion: 1,
        idempotencyKey: editor.delivery.idempotencyKey,
        text: editor.text,
        clientCreatedAt: editor.delivery.clientCreatedAt,
      })
      editor.clearAfterConfirmedSend()
    } catch (error) {
      authentication.handleApiError(error)
    }
  }

  return (
    <PageLayout
      actions={
        <Link
          className={buttonVariants({ size: 'sm', variant: 'outline' })}
          search={{ state: 'awaiting_staff' }}
          to="/questions"
        >
          Назад к вопросам
        </Link>
      }
      description={[thread.student.displayName, thread.context.courseName, thread.context.groupName]
        .filter(Boolean)
        .join(' · ')}
      eyebrow="Приватная переписка"
      title={thread.context.problemTitle ?? 'Общий вопрос по занятию'}
      width="content"
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <FeedbackThread
          messages={thread.entries.map((entry) => staffMessage(entry, principal.userId))}
        />
        <Card className="h-fit lg:sticky lg:top-4">
          <CardContent className="pt-4">
            <SupportComposer
              busy={mutation.isPending}
              density="compact"
              error={mutation.error ? describeSupportError(mutation.error) : null}
              onSubmit={() => void submit()}
              onValueChange={(value) => {
                mutation.reset()
                editor.setText(value)
              }}
              saveState={editor.saveState}
              submitLabel="Ответить"
              value={editor.text}
            />
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}

function staffMessage(entry: SupportEntry, staffUserId: string): ThreadMessageView {
  return {
    id: entry.entryId,
    author: { kind: entry.author.kind, name: entry.author.displayName },
    at: formatSupportTime(entry.receivedAt),
    channel: entry.channel,
    body: entry.text ?? 'Приложено изображение.',
    own: entry.author.userId === staffUserId,
  }
}

function supportContext(item: SupportThreadSummary): string {
  return [item.context.courseName, item.context.groupName].filter(Boolean).join(' · ')
}

function formatSupportTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function supportErrorState(error: unknown): 'offline' | 'forbidden' | 'empty' | 'error' {
  if (error instanceof SupportNetworkError) return 'offline'
  if (error instanceof ApiResponseError && error.status === 403) return 'forbidden'
  if (error instanceof ApiResponseError && error.status === 404) return 'empty'
  return 'error'
}

function describeSupportError(error: unknown): string {
  if (error instanceof SupportNetworkError) {
    return 'Нет связи с сервером. Набранный ответ остаётся на этом устройстве.'
  }
  if (error instanceof ApiResponseError) return error.message
  return 'Не удалось обновить переписку. Набранный ответ не удалён.'
}

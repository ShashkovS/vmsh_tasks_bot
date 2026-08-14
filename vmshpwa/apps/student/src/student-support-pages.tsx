import { Link, useNavigate } from '@tanstack/react-router'
import { MessageCircleQuestion } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  SupportNetworkError,
  createSupportClient,
  useAppendSupportEntryMutation,
  useAuthenticatedPrincipal,
  useAuthentication,
  useCreateSupportThreadMutation,
  useStudentSupportThreadsInfiniteQuery,
  useSupportThreadQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type SupportEntry, type SupportThreadSummary } from '@vmsh/contracts'
import { useSupportDraftEditor, type SupportDraftDescriptor } from '@vmsh/offline'
import { FeedbackThread, SupportComposer, type ThreadMessageView } from '@vmsh/product'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, buttonVariants } from '@vmsh/ui'

/** Live Student questions UI; see Phase 6 Questions/SOS and support API proof. */
export function StudentSupportInboxPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student questions require Student auth')
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
  const query = useStudentSupportThreadsInfiniteQuery(client, principal)
  const items = query.data?.pages.flatMap((page) => page.items) ?? []

  let content
  if (query.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (query.error) {
    content = (
      <PageStatePanel
        actionLabel="Повторить"
        description={describeSupportError(query.error)}
        onAction={() => void query.refetch()}
        state={supportErrorState(query.error)}
      />
    )
  } else if (items.length === 0) {
    content = (
      <PageStatePanel
        description="Вопрос к задаче можно задать прямо со страницы этой задачи. Переписка появится здесь."
        state="empty"
        title="Вопросов пока нет"
      />
    )
  } else {
    content = (
      <div className="space-y-3">
        <ol className="space-y-2" aria-label="Ваши вопросы">
          {items.map((item) => (
            <StudentSupportSummary item={item} key={item.threadId} />
          ))}
        </ol>
        {query.hasNextPage ? (
          <Button
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
            size="sm"
            variant="outline"
          >
            {query.isFetchingNextPage ? 'Загружаем…' : 'Показать более ранние'}
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <PageLayout
      description="Приватная переписка видна только вам и преподавателям, у которых есть доступ к вашей группе."
      eyebrow="Помощь"
      title="Ваши вопросы"
      width="reading"
    >
      {content}
    </PageLayout>
  )
}

function StudentSupportSummary({ item }: { item: SupportThreadSummary }) {
  const title = item.context.problemTitle ?? 'Общий вопрос по занятию'
  return (
    <li>
      <Link
        className="block rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        params={{ threadId: item.threadId }}
        to="/questions/$threadId"
      >
        <Card className="transition-colors hover:bg-surface-subtle" size="sm">
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            <Badge variant={item.replyState === 'awaiting_student' ? 'info' : 'neutral'}>
              {item.replyState === 'awaiting_student' ? 'Есть ответ' : 'Ждём преподавателя'}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-1">
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

export function StudentNewSupportPage({
  groupLessonId,
  problemId,
}: {
  groupLessonId: string
  problemId?: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student questions require Student auth')
  const navigate = useNavigate()
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
  const descriptor = useMemo<SupportDraftDescriptor>(
    () => ({
      ownerAccountId: principal.accountId,
      target: problemId
        ? { kind: 'new_problem_question', groupLessonId, problemId }
        : { kind: 'new_general_question', groupLessonId },
    }),
    [groupLessonId, principal.accountId, problemId],
  )
  const editor = useSupportDraftEditor(
    { audience: 'student', instance: authentication.client.runtime.instance },
    descriptor,
  )
  const mutation = useCreateSupportThreadMutation(client, principal)
  const threadList = useStudentSupportThreadsInfiniteQuery(client, principal)
  const existingThread = threadList.data?.pages
    .flatMap((page) => page.items)
    .find(
      (thread) =>
        thread.context.groupLessonId === groupLessonId &&
        thread.context.problemId === (problemId ?? null),
    )

  useEffect(() => {
    if (existingThread) {
      void navigate({
        to: '/questions/$threadId',
        params: { threadId: existingThread.threadId },
        replace: true,
      })
    } else if (threadList.hasNextPage && !threadList.isFetchingNextPage) {
      void threadList.fetchNextPage()
    }
  }, [existingThread, navigate, threadList])

  const submit = async () => {
    mutation.reset()
    try {
      const response = await mutation.mutateAsync({
        schemaVersion: 1,
        idempotencyKey: editor.delivery.idempotencyKey,
        kind: problemId ? 'problem_question' : 'general',
        groupLessonId,
        problemId: problemId ?? null,
        text: editor.text,
        clientCreatedAt: editor.delivery.clientCreatedAt,
      })
      editor.clearAfterConfirmedSend()
      await navigate({
        to: '/questions/$threadId',
        params: { threadId: response.thread.threadId },
        replace: true,
      })
    } catch (error) {
      authentication.handleApiError(error)
    }
  }

  if (threadList.isPending || threadList.hasNextPage || existingThread) {
    return (
      <PageLayout title="Вопрос" width="reading">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      actions={
        <Link className={buttonVariants({ size: 'sm', variant: 'outline' })} to="/questions">
          История вопросов
        </Link>
      }
      description={
        problemId
          ? 'Напишите, какой переход или часть условия вызывает вопрос.'
          : 'Этот вопрос относится к занятию целиком.'
      }
      eyebrow={problemId ? 'Вопрос к задаче' : 'Общий вопрос'}
      title="Спросить преподавателя"
      width="reading"
    >
      <Card>
        <CardContent className="pt-4">
          <SupportComposer
            busy={mutation.isPending}
            error={mutation.error ? describeSupportError(mutation.error) : null}
            onSubmit={() => void submit()}
            onValueChange={(value) => {
              mutation.reset()
              editor.setText(value)
            }}
            saveState={editor.saveState}
            value={editor.text}
          />
        </CardContent>
      </Card>
    </PageLayout>
  )
}

export function StudentSupportThreadPage({ threadId }: { threadId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student questions require Student auth')
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
    { audience: 'student', instance: authentication.client.runtime.instance },
    descriptor,
  )

  if (query.isPending) {
    return (
      <PageLayout title="Вопрос" width="reading">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    return (
      <PageLayout title="Вопрос" width="reading">
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
        <Link className={buttonVariants({ size: 'sm', variant: 'outline' })} to="/questions">
          Все вопросы
        </Link>
      }
      description={supportThreadContext(thread.context)}
      eyebrow="Приватная переписка"
      title={thread.context.problemTitle ?? 'Общий вопрос по занятию'}
      width="reading"
    >
      <div className="space-y-5">
        <FeedbackThread
          messages={thread.entries.map((entry) => studentMessage(entry, principal.userId))}
        />
        <Card>
          <CardContent className="pt-4">
            <SupportComposer
              busy={mutation.isPending}
              error={mutation.error ? describeSupportError(mutation.error) : null}
              onSubmit={() => void submit()}
              onValueChange={(value) => {
                mutation.reset()
                editor.setText(value)
              }}
              saveState={editor.saveState}
              submitLabel="Дополнить вопрос"
              value={editor.text}
            />
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}

function studentMessage(entry: SupportEntry, studentUserId: string): ThreadMessageView {
  return {
    id: entry.entryId,
    author: { kind: entry.author.kind, name: entry.author.displayName },
    at: formatSupportTime(entry.receivedAt),
    channel: entry.channel,
    body: entry.text ?? 'Приложено изображение.',
    own: entry.author.userId === studentUserId,
  }
}

function supportContext(item: SupportThreadSummary): string {
  return [item.context.courseName, item.context.groupName].filter(Boolean).join(' · ')
}

function supportThreadContext(context: SupportThreadSummary['context']): string {
  return [context.courseName, context.groupName].filter(Boolean).join(' · ')
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
    return 'Нет связи с сервером. Набранный текст остаётся на этом устройстве.'
  }
  if (error instanceof ApiResponseError) return error.message
  return 'Не удалось обновить переписку. Набранный текст не удалён.'
}

export function StudentProblemQuestionLink({
  groupLessonId,
  problemId,
}: {
  groupLessonId: string
  problemId: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student questions require Student auth')
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
  const list = useStudentSupportThreadsInfiniteQuery(client, principal)
  const matchingThread = list.data?.pages
    .flatMap((page) => page.items)
    .find(
      (thread) =>
        thread.context.groupLessonId === groupLessonId && thread.context.problemId === problemId,
    )
  const [createdThreadId, setCreatedThreadId] = useState<string>()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!matchingThread && list.hasNextPage && !list.isFetchingNextPage) {
      void list.fetchNextPage()
    }
  }, [list, matchingThread])

  const threadId = createdThreadId ?? matchingThread?.threadId
  return (
    <section aria-label="Обсуждение задачи" className="mt-4 border-t border-border pt-3">
      <Button
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        size="sm"
        variant="ghost"
      >
        <MessageCircleQuestion aria-hidden="true" className="size-4" />
        {threadId ? 'Переписка с преподавателем' : 'Задать вопрос'}
      </Button>
      {open ? (
        <div className="mt-3">
          {threadId ? (
            <InlineStudentSupportThread client={client} threadId={threadId} />
          ) : list.isPending || list.hasNextPage ? (
            <p className="text-small text-muted-foreground">Загружаем предыдущие вопросы…</p>
          ) : (
            <InlineNewProblemQuestion
              client={client}
              groupLessonId={groupLessonId}
              onCreated={setCreatedThreadId}
              problemId={problemId}
            />
          )}
        </div>
      ) : null}
    </section>
  )
}

function InlineNewProblemQuestion({
  client,
  groupLessonId,
  onCreated,
  problemId,
}: {
  client: ReturnType<typeof createSupportClient>
  groupLessonId: string
  onCreated: (threadId: string) => void
  problemId: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student questions require Student auth')
  const descriptor = useMemo<SupportDraftDescriptor>(
    () => ({
      ownerAccountId: principal.accountId,
      target: { kind: 'new_problem_question', groupLessonId, problemId },
    }),
    [groupLessonId, principal.accountId, problemId],
  )
  const editor = useSupportDraftEditor(
    { audience: 'student', instance: authentication.client.runtime.instance },
    descriptor,
  )
  const mutation = useCreateSupportThreadMutation(client, principal)
  const submit = async () => {
    mutation.reset()
    try {
      const response = await mutation.mutateAsync({
        schemaVersion: 1,
        idempotencyKey: editor.delivery.idempotencyKey,
        kind: 'problem_question',
        groupLessonId,
        problemId,
        text: editor.text,
        clientCreatedAt: editor.delivery.clientCreatedAt,
      })
      editor.clearAfterConfirmedSend()
      onCreated(response.thread.threadId)
    } catch (error) {
      authentication.handleApiError(error)
    }
  }
  return (
    <SupportComposer
      busy={mutation.isPending}
      error={mutation.error ? describeSupportError(mutation.error) : null}
      onSubmit={() => void submit()}
      onValueChange={(value) => {
        mutation.reset()
        editor.setText(value)
      }}
      saveState={editor.saveState}
      submitLabel="Отправить вопрос"
      value={editor.text}
    />
  )
}

function InlineStudentSupportThread({
  client,
  threadId,
}: {
  client: ReturnType<typeof createSupportClient>
  threadId: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student questions require Student auth')
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
    { audience: 'student', instance: authentication.client.runtime.instance },
    descriptor,
  )
  if (query.isPending) {
    return <p className="text-small text-muted-foreground">Загружаем переписку…</p>
  }
  if (query.error) {
    return (
      <p className="text-small text-danger" role="alert">
        {describeSupportError(query.error)}
      </p>
    )
  }
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
    <div className="space-y-4">
      <FeedbackThread
        messages={query.data.thread.entries.map((entry) => studentMessage(entry, principal.userId))}
      />
      <SupportComposer
        busy={mutation.isPending}
        error={mutation.error ? describeSupportError(mutation.error) : null}
        onSubmit={() => void submit()}
        onValueChange={(value) => {
          mutation.reset()
          editor.setText(value)
        }}
        saveState={editor.saveState}
        submitLabel="Дополнить вопрос"
        value={editor.text}
      />
    </div>
  )
}

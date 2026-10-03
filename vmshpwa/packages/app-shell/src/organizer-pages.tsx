import { formatDateTime } from '@vmsh/i18n'
import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { QuestionPhotoPicker } from '@vmsh/product'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FeedbackThread, ZoomableFigure, type ThreadMessageView } from '@vmsh/product'
import { ApiResponseError } from '@vmsh/contracts'
import { useOrganizerDraft } from '@vmsh/offline'
import { Button, Card, CardContent, Textarea, buttonVariants } from '@vmsh/ui'
import { useAuthenticatedPrincipal, useAuthentication } from './auth-context'
import { useOrganizerClient, useOrganizerCount } from './organizer-client'

/** Student/Family/Staff orchestration; docs/organizer-questions.md. */
export function OrganizerLink({ create = false }: { create?: boolean }) {
  const p = useAuthenticatedPrincipal()
  const count = useOrganizerCount(p.accountId)
  const href = `/${p.audience}/${p.audience === 'staff' ? 'questions/organizers' : 'organizers'}`
  return (
    <a
      className={buttonVariants({ variant: 'outline', size: 'sm' })}
      href={`${href}${create ? '/new' : ''}`}
    >
      {create ? t`Задать вопрос организаторам` : t`Вопросы организаторам`}
      {!create && count.data ? <span aria-label={t`Непрочитанных`}> · {count.data}</span> : null}
    </a>
  )
}

export function OrganizerPage({
  threadId,
  isNew = false,
  state = 'awaiting_staff',
  onNavigate,
}: {
  threadId?: string | undefined
  isNew?: boolean
  state?: string
  onNavigate: (id?: string, create?: boolean, state?: string) => void
}) {
  const p = useAuthenticatedPrincipal()
  if (p.audience === 'staff' && p.role !== 'admin')
    return (
      <p role="alert">
        <Trans>Обращения доступны только администраторам.</Trans>
      </p>
    )
  return (
    <OrganizerPageContent
      key={`${p.audience}:${p.accountId}:${threadId ?? (isNew ? 'new' : 'list')}`}
      threadId={threadId}
      isNew={isNew}
      state={state}
      onNavigate={onNavigate}
    />
  )
}
function OrganizerPageContent({
  threadId,
  isNew,
  state,
  onNavigate,
}: {
  threadId?: string | undefined
  isNew: boolean
  state: string
  onNavigate: (id?: string, create?: boolean, state?: string) => void
}) {
  const p = useAuthenticatedPrincipal()
  const client = useOrganizerClient()
  const staff = p.audience === 'staff'
  const queryClient = useQueryClient()
  const list = useInfiniteQuery({
    queryKey: ['organizer-questions', p.accountId, 'list', staff ? state : 'all'],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => client.list(staff ? state : 'all', pageParam),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: !threadId && !isNew,
    meta: { realtimeResources: ['organizer-questions'] },
    refetchOnWindowFocus: 'always',
  })
  const thread = useInfiniteQuery({
    queryKey: ['organizer-questions', p.accountId, threadId],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => client.thread(threadId!, pageParam),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: !!threadId,
    meta: { realtimeResources: [`organizer-questions/${threadId}`] },
    refetchOnWindowFocus: 'always',
  })
  const messages = useMemo(
    () => thread.data?.pages.flatMap((page) => page.entries) ?? [],
    [thread.data],
  )
  const summary = thread.data?.pages[0]?.thread
  const readSequence = useRef(0)
  useEffect(() => {
    const sequence = messages.at(-1)?.sequence ?? 0
    if (!staff && threadId && sequence > readSequence.current && !thread.hasNextPage) {
      const timer = setTimeout(() => {
        if (document.visibilityState !== 'visible') return
        void client
          .read(threadId, sequence)
          .then(() => {
            readSequence.current = sequence
            void queryClient.invalidateQueries({
              queryKey: ['organizer-questions', p.accountId, 'count'],
            })
          })
          .catch(() => {})
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [messages, staff, threadId, thread.hasNextPage, client, queryClient, p.accountId])
  const query = threadId ? thread : list
  const loading = !isNew && query.isPending
  const error = !isNew && query.error
  const items = list.data?.pages.flatMap((page) => page.items) ?? []
  const views: ThreadMessageView[] = messages.map((entry) => ({
    id: entry.entryId,
    author: {
      kind: entry.author.audience === 'staff' ? 'admin' : entry.author.audience,
      name: entry.author.name,
    },
    at: formatDateTime(new Date(entry.createdAt)),
    channel: entry.author.audience === 'staff' ? 'staff' : 'pwa',
    own: staff === (entry.author.audience === 'staff'),
    body: (
      <div className="min-w-0 space-y-2">
        <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{entry.text}</p>
        {entry.photos.map((photo) => (
          <ZoomableFigure key={photo.photoId} alt={t`Фотография в обращении`}>
            <img
              loading="lazy"
              src={photo.url}
              width={photo.width}
              height={photo.height}
              className="h-auto max-w-full"
              alt={t`Фотография в обращении`}
            />
          </ZoomableFigure>
        ))}
      </div>
    ),
  }))
  return (
    <section
      className={
        staff
          ? 'mx-auto w-full max-w-[1500px] space-y-4 px-4 py-5 sm:px-6 sm:py-7'
          : 'mx-auto w-full max-w-3xl space-y-4 p-3 sm:p-5'
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <h1 className="text-title font-semibold tracking-tight">
          {isNew ? t`Задать вопрос организаторам` : t`Вопросы организаторам`}
        </h1>
        <div className="flex flex-wrap gap-2">
          {threadId || isNew ? (
            <Button variant="ghost" size="sm" onClick={() => onNavigate()}>
              <Trans>Все обращения</Trans>
            </Button>
          ) : !staff ? (
            <Button size="sm" onClick={() => onNavigate(undefined, true)}>
              <Trans>Задать вопрос</Trans>
            </Button>
          ) : null}
          {!isNew ? (
            <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
              <Trans>Обновить</Trans>
            </Button>
          ) : null}
        </div>
      </div>
      <p className="text-small text-muted-foreground">
        <Trans>Переписку видят только автор обращения и администраторы.</Trans>
      </p>
      {staff && !threadId ? (
        <nav className="flex flex-wrap gap-1" aria-label={t`Состояние обращения`}>
          {[
            ['awaiting_staff', t`Нужен ответ`],
            ['answered', t`Ответили`],
            ['all', t`Все`],
          ].map(([value, label]) => (
            <Button
              key={value}
              size="sm"
              variant={state === value ? 'secondary' : 'ghost'}
              onClick={() => onNavigate(undefined, false, value)}
            >
              {label}
            </Button>
          ))}
        </nav>
      ) : null}
      {loading ? (
        <p role="status">
          <Trans>Загружаем…</Trans>
        </p>
      ) : null}
      {error ? (
        <div role="alert">
          <Trans>Не удалось загрузить переписку. Проверьте подключение и нажмите «Обновить».</Trans>
        </div>
      ) : null}
      {!loading && !error && !threadId && !isNew ? (
        <>
          <ol className={staff ? 'grid gap-3 lg:grid-cols-2' : 'space-y-2'}>
            {items.map((item) => (
              <li key={item.threadId}>
                <button
                  className="h-full w-full space-y-2 rounded-lg border border-border bg-surface p-4 text-left hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  onClick={() => onNavigate(item.threadId)}
                >
                  <span className="block break-words font-medium">{item.title}</span>
                  {staff ? (
                    <span className="block text-small">
                      {item.owner.name} ·{' '}
                      {item.owner.audience === 'family' ? t`Родитель` : t`Школьник`}
                      {item.child ? ` · ${item.child.name}` : ''}
                    </span>
                  ) : null}
                  <span className="block line-clamp-2 break-words text-small text-muted-foreground">
                    {item.latestText || t`Фотография`}
                  </span>
                  <span className="text-caption text-muted-foreground">
                    {item.state === 'awaiting_staff' ? t`Нужен ответ` : t`Ответили`} ·{' '}
                    {formatDateTime(new Date(item.latestAt))}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {!items.length ? (
            <p>
              <Trans>Обращений пока нет.</Trans>
            </p>
          ) : null}
          {list.hasNextPage ? (
            <Button
              variant="outline"
              disabled={list.isFetchingNextPage}
              onClick={() => void list.fetchNextPage()}
            >
              <Trans>Показать ещё</Trans>
            </Button>
          ) : null}
        </>
      ) : null}
      {summary ? (
        <>
          <p className="text-small">
            {summary.title}
            {staff ? ` · ${summary.owner.name}` : ''}
            {summary.child ? ` · ${summary.child.name}` : ''}
          </p>
          <FeedbackThread messages={views} />
          {thread.hasNextPage ? (
            <Button
              variant="outline"
              disabled={thread.isFetchingNextPage}
              onClick={() => void thread.fetchNextPage()}
            >
              <Trans>Показать ещё сообщения</Trans>
            </Button>
          ) : null}
        </>
      ) : null}
      {isNew || summary ? (
        <OrganizerCompose
          threadId={threadId}
          onSent={async (id) => {
            await queryClient.invalidateQueries({ queryKey: ['organizer-questions', p.accountId] })
            if (isNew) onNavigate(id)
          }}
        />
      ) : null}
    </section>
  )
}
function OrganizerCompose({
  threadId,
  onSent,
}: {
  threadId?: string | undefined
  onSent: (id: string) => Promise<void>
}) {
  const p = useAuthenticatedPrincipal()
  const auth = useAuthentication()
  const client = useOrganizerClient()
  const editor = useOrganizerDraft(
    `${auth.client.runtime.instance}:${p.audience}:${p.accountId}`,
    threadId ?? 'new',
  )
  const { draft } = editor
  const [error, setError] = useState('')
  const mutation = useMutation({
    networkMode: 'always',
    mutationFn: async () => {
      if (!navigator.onLine) throw new Error('offline')
      const photoIds = []
      for (let index = 0; index < draft.photos.length; index++) {
        const id =
          draft.uploadedIds[index] ?? (await client.upload(draft.photos[index]!)).photo.photoId
        photoIds.push(id)
        editor.update({ ...draft, uploadedIds: [...photoIds] })
      }
      const result = await client.send(threadId, {
        text: draft.text,
        photoIds,
        idempotencyKey: draft.idempotencyKey,
        childId: threadId ? null : draft.childId,
      })
      await editor.clear()
      await onSent(result.threadId)
    },
    onError: (failure) =>
      setError(
        failure instanceof ApiResponseError
          ? t`Сообщение не отправлено. ${failure.message}`
          : t`Сообщение не отправлено. Текст и фотографии остаются в форме. Проверьте подключение и повторите отправку.`,
      ),
  })
  const submit = () => {
    if (!mutation.isPending && editor.ready && (draft.text.trim() || draft.photos.length)) {
      setError('')
      mutation.mutate()
    }
  }
  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          {!threadId && p.audience === 'family' ? (
            <label className="block text-small">
              <Trans>О ком вопрос</Trans>
              <select
                disabled={mutation.isPending || !editor.ready}
                className="mt-1 block min-h-10 w-full rounded border border-input bg-surface p-2"
                value={draft.childId ?? ''}
                onChange={(event) =>
                  editor.update({ ...draft, childId: event.target.value || null })
                }
              >
                <option value="">
                  <Trans>Общий вопрос</Trans>
                </option>
                {p.linkedChildren.map((child) => (
                  <option key={child.studentId} value={child.studentId}>
                    {child.displayName}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <Textarea
            aria-label={t`Сообщение организаторам`}
            placeholder={t`Напишите ваш вопрос…`}
            maxLength={100000}
            rows={4}
            disabled={mutation.isPending || !editor.ready}
            value={draft.text}
            onChange={(event) => editor.update({ ...draft, text: event.target.value })}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                event.preventDefault()
                submit()
              }
            }}
          />
          <QuestionPhotoPicker
            action={
              <Button
                type="submit"
                className="min-w-0 max-w-full"
                disabled={
                  mutation.isPending ||
                  !editor.ready ||
                  (!draft.text.trim() && !draft.photos.length)
                }
              >
                {mutation.isPending ? t`Отправляем…` : t`Отправить`}
              </Button>
            }
            photos={draft.photos}
            disabled={mutation.isPending || !editor.ready}
            onChange={(photos, removedIndex) =>
              editor.update({
                ...draft,
                photos,
                uploadedIds:
                  removedIndex === undefined
                    ? draft.uploadedIds
                    : draft.uploadedIds.filter((_, i) => i !== removedIndex),
              })
            }
          />
          <div>
            <p role="status" className="text-caption text-muted-foreground">
              {editor.unavailable
                ? t`Черновик не сохраняется. Не закрывайте страницу.`
                : editor.saved
                  ? t`Черновик сохранён на устройстве.`
                  : ''}
            </p>
          </div>
          {error ? (
            <p role="alert" className="text-small text-danger">
              {error}
            </p>
          ) : null}
        </form>
      </CardContent>
    </Card>
  )
}

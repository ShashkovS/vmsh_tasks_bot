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
      {create ? 'Задать вопрос организаторам' : 'Вопросы организаторам'}
      {!create && count.data ? <span aria-label="Непрочитанных"> · {count.data}</span> : null}
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
    return <p role="alert">Обращения доступны только администраторам.</p>
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
    at: new Date(entry.createdAt).toLocaleString('ru-RU'),
    channel: entry.author.audience === 'staff' ? 'staff' : 'pwa',
    own: staff === (entry.author.audience === 'staff'),
    body: (
      <div className="min-w-0 space-y-2">
        <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{entry.text}</p>
        {entry.photos.map((photo) => (
          <ZoomableFigure key={photo.photoId} alt="Фотография в обращении">
            <img
              loading="lazy"
              src={photo.url}
              width={photo.width}
              height={photo.height}
              className="h-auto max-w-full"
              alt="Фотография в обращении"
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
          {isNew ? 'Задать вопрос организаторам' : 'Вопросы организаторам'}
        </h1>
        <div className="flex flex-wrap gap-2">
          {threadId || isNew ? (
            <Button variant="ghost" size="sm" onClick={() => onNavigate()}>
              Все обращения
            </Button>
          ) : !staff ? (
            <Button size="sm" onClick={() => onNavigate(undefined, true)}>
              Задать вопрос
            </Button>
          ) : null}
          {!isNew ? (
            <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
              Обновить
            </Button>
          ) : null}
        </div>
      </div>
      <p className="text-small text-muted-foreground">
        Переписку видят только автор обращения и администраторы.
      </p>
      {staff && !threadId ? (
        <nav className="flex flex-wrap gap-1" aria-label="Состояние обращения">
          {[
            ['awaiting_staff', 'Нужен ответ'],
            ['answered', 'Ответили'],
            ['all', 'Все'],
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
      {loading ? <p role="status">Загружаем…</p> : null}
      {error ? (
        <div role="alert">
          Не удалось загрузить переписку. Проверьте подключение и нажмите «Обновить».
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
                      {item.owner.audience === 'family' ? 'Родитель' : 'Школьник'}
                      {item.child ? ` · ${item.child.name}` : ''}
                    </span>
                  ) : null}
                  <span className="block line-clamp-2 break-words text-small text-muted-foreground">
                    {item.latestText || 'Фотография'}
                  </span>
                  <span className="text-caption text-muted-foreground">
                    {item.state === 'awaiting_staff' ? 'Нужен ответ' : 'Ответили'} ·{' '}
                    {new Date(item.latestAt).toLocaleString('ru-RU')}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {!items.length ? <p>Обращений пока нет.</p> : null}
          {list.hasNextPage ? (
            <Button
              variant="outline"
              disabled={list.isFetchingNextPage}
              onClick={() => void list.fetchNextPage()}
            >
              Показать ещё
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
              Показать ещё сообщения
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
function PhotoPreview({ blob }: { blob: Blob }) {
  const imageRef = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const next = URL.createObjectURL(blob)
    if (imageRef.current) imageRef.current.src = next
    return () => URL.revokeObjectURL(next)
  }, [blob])
  return (
    <img ref={imageRef} alt="Выбранная фотография" className="h-20 w-20 rounded object-cover" />
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
          ? `Сообщение не отправлено. ${failure.message}`
          : 'Сообщение не отправлено. Текст и фотографии остаются в форме. Проверьте подключение и повторите отправку.',
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
              О ком вопрос
              <select
                disabled={mutation.isPending || !editor.ready}
                className="mt-1 block min-h-10 w-full rounded border border-input bg-surface p-2"
                value={draft.childId ?? ''}
                onChange={(event) =>
                  editor.update({ ...draft, childId: event.target.value || null })
                }
              >
                <option value="">Общий вопрос</option>
                {p.linkedChildren.map((child) => (
                  <option key={child.studentId} value={child.studentId}>
                    {child.displayName}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <Textarea
            aria-label="Сообщение организаторам"
            placeholder="Напишите ваш вопрос…"
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
          <div className="flex flex-wrap gap-2">
            {draft.photos.map((blob, index) => (
              <div key={index}>
                <PhotoPreview blob={blob} />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={mutation.isPending}
                  onClick={() =>
                    editor.update({
                      ...draft,
                      photos: draft.photos.filter((_, i) => i !== index),
                      uploadedIds: draft.uploadedIds.filter((_, i) => i !== index),
                    })
                  }
                  aria-label={`Убрать фотографию ${index + 1}`}
                >
                  Убрать
                </Button>
              </div>
            ))}
          </div>
          <label className="block text-small">
            Прикрепить фотографии
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              disabled={mutation.isPending || !editor.ready}
              className="mt-1 block w-full max-w-full text-small"
              onChange={(event) => {
                const files = Array.from(event.target.files ?? [])
                event.target.value = ''
                if (
                  files.length + draft.photos.length > 10 ||
                  files.some(
                    (file) =>
                      file.size > 25 * 1024 * 1024 ||
                      !['image/jpeg', 'image/png', 'image/webp'].includes(file.type),
                  )
                ) {
                  setError(
                    'Можно прикрепить до 10 фотографий JPEG, PNG или WebP размером до 25 МиБ каждая.',
                  )
                  return
                }
                setError('')
                editor.update({ ...draft, photos: [...draft.photos, ...files] })
              }}
            />
          </label>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p role="status" className="text-caption text-muted-foreground">
              {editor.unavailable
                ? 'Черновик не сохраняется. Не закрывайте страницу.'
                : editor.saved
                  ? 'Черновик сохранён на устройстве.'
                  : ''}
            </p>
            <Button
              type="submit"
              disabled={
                mutation.isPending || !editor.ready || (!draft.text.trim() && !draft.photos.length)
              }
            >
              {mutation.isPending ? 'Отправляем…' : 'Отправить'}
            </Button>
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

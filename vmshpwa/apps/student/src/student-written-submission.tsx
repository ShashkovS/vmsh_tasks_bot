import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CloudOff, Pencil, TriangleAlert } from 'lucide-react'

import {
  createWrittenSubmissionClient,
  useAuthentication,
  useWrittenStudentReactionMutation,
  useWrittenThreadQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type StudentProblemType,
  type WrittenEntry,
  type WrittenReviewProjection,
  type WrittenThread,
} from '@vmsh/contracts'
import {
  createWrittenSubmissionDraftStore,
  createWrittenSubmissionOutbox,
  useOfflineDatabase,
  type ResolvedWrittenDraftPhoto,
  type WrittenDraftDescriptor,
  type WrittenDraftReplacementTarget,
  type WrittenSubmissionOutboxItem,
} from '@vmsh/offline'
import {
  ChatComposer,
  ReactionChip,
  ReactionPicker,
  ReviewAnnotationViewer,
  TaskChat,
  findReaction,
  reactionsForScope,
  writtenReviewVerdict,
  type AttachmentView,
  type ChatMessageView,
} from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  Skeleton,
  Textarea,
} from '@vmsh/ui'

import { compressWrittenSubmissionImage } from './image-compression'
import { announceSafePwaUpdateMoment } from './pwa-update-events'
import {
  buildWrittenChatItems,
  chatDate,
  chatTime,
  replaceableWrittenEntry,
} from './student-written-chat'

/**
 * Canonical Phase-5 Student composer. Significant edits are persisted before
 * the UI claims success; remote create/upload/reorder/submit is resumed by the
 * durable outbox. See `dev/development-plan/09-phase-5-written-submissions.md`.
 */

interface PendingPhoto {
  id: string
  name: string
  status: 'processing' | 'failed'
  error?: string
}

interface StudentWrittenSubmissionProps {
  problemId: string
  problemType: Extract<StudentProblemType, 'written' | 'oral'>
  conditionRevisionId: string
  configVersion: number
  closed?: boolean
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`
  return `${(bytes / (1024 * 1024)).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} МБ`
}

function deliveryMessage(error: unknown): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof Error && error.name === 'WrittenSubmissionLocalEvidenceError') {
    return 'Одна из сохранённых фотографий недоступна. Добавьте её заново.'
  }
  return 'Не удалось отправить решение. Оно сохранено на этом устройстве.'
}

function relevantItem(
  items: WrittenSubmissionOutboxItem[],
  descriptor: WrittenDraftDescriptor,
): WrittenSubmissionOutboxItem | null {
  return (
    items.find(
      (item) =>
        item.payload.descriptor.problemId === descriptor.problemId &&
        item.payload.descriptor.conditionRevisionId === descriptor.conditionRevisionId &&
        item.payload.descriptor.configVersion === descriptor.configVersion,
    ) ?? null
  )
}

function usePhotoPreviewUrls(photos: ResolvedWrittenDraftPhoto[]): Map<string, string> {
  const urls = useMemo(
    () => new Map(photos.map((photo) => [photo.id, URL.createObjectURL(photo.blob)] as const)),
    [photos],
  )
  useEffect(() => {
    return () => {
      for (const url of urls.values()) URL.revokeObjectURL(url)
    }
  }, [urls])
  return urls
}

function EntryPhotos({ entry }: { entry: WrittenEntry }) {
  return (
    <ol className="flex flex-wrap gap-1.5">
      {[...entry.attachments]
        .sort((left, right) => left.ordinal - right.ordinal)
        .map((attachment, index) => (
          <li key={attachment.attachmentId}>
            <a href={attachment.mediaPath} rel="noreferrer" target="_blank">
              <img
                alt={`Страница ${index + 1}`}
                className="max-h-32 rounded border border-border bg-surface-sunken"
                loading="lazy"
                src={attachment.mediaPath}
              />
            </a>
          </li>
        ))}
    </ol>
  )
}

function ReviewAnnotations({ review, thread }: { review: WrittenReviewProjection; thread: WrittenThread }) {
  const attachments = new Map(
    thread.entries.flatMap((entry) =>
      entry.attachments.map((attachment) => [attachment.attachmentId, attachment] as const),
    ),
  )
  return (
    <div className="space-y-2">
      {review.annotations.map((annotation, index) => {
        const attachment = attachments.get(annotation.attachmentId)
        if (!attachment) return null
        return (
          <ReviewAnnotationViewer
            imageAlt={`Проверенная страница решения ${index + 1}`}
            imageSource={attachment.mediaPath}
            key={`${review.reviewId}:${annotation.attachmentId}`}
            manifest={annotation}
          />
        )
      })}
    </div>
  )
}

function ReviewReactions({
  review,
  now,
  onReaction,
  pending,
  error,
}: {
  review: WrittenReviewProjection
  now: number
  onReaction: (reviewId: string, reactionId: 0 | 1 | 2 | null, expectedVersion: number) => void
  pending: boolean
  error: string | null
}) {
  const current =
    review.studentReaction?.reactionId == null
      ? null
      : findReaction(review.studentReaction.reactionId)
  const editableUntil =
    review.studentReaction?.editableUntil ??
    new Date(new Date(review.completedAt).getTime() + 60 * 60 * 1000).toISOString()
  return (
    <div className="space-y-1">
      {now <= Date.parse(editableUntil) ? (
        <ReactionPicker
          disabled={pending}
          legend="Ваша реакция на проверку"
          onSelect={(reactionId) =>
            onReaction(
              review.reviewId,
              reactionId as 0 | 1 | 2 | null,
              review.studentReaction?.version ?? 0,
            )
          }
          options={reactionsForScope('student-written')}
          value={review.studentReaction?.reactionId ?? null}
        />
      ) : current ? (
        <div className="space-y-1">
          <p className="text-caption text-muted-foreground">Ваша реакция</p>
          <ReactionChip reaction={current} />
        </div>
      ) : null}
      {error ? (
        <p className="text-small text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

/** One conversation per task: own material, teacher or bot answers, verdicts. */
function writtenChatMessages({
  thread,
  now,
  onReaction,
  pendingReactionReviewId,
  reactionError,
}: {
  thread: WrittenThread | null
  now: number
  onReaction: (reviewId: string, reactionId: 0 | 1 | 2 | null, expectedVersion: number) => void
  pendingReactionReviewId: string | null
  reactionError: { reviewId: string; message: string } | null
}): ChatMessageView[] {
  if (!thread) return []
  return buildWrittenChatItems(thread).map(({ key, at, entry, review }) => {
    const base = { id: key, at: chatTime(at), dateLabel: chatDate(at) }
    if (entry?.authorKind === 'student') {
      return {
        ...base,
        author: 'student' as const,
        own: true,
        ...(entry.text?.trim() ? { text: entry.text } : {}),
        ...(entry.attachments.length > 0 ? { media: <EntryPhotos entry={entry} /> } : {}),
        delivery: 'sent' as const,
        ...(entry.version > 1 ? { edited: true } : {}),
      }
    }
    if (entry && entry.entryKind === 'system_event') {
      return {
        ...base,
        author: 'system' as const,
        text: entry.text ?? 'Событие по задаче',
      }
    }
    const ai = review?.source === 'ai' || entry?.authorKind === 'ai'
    const text = entry?.text ?? review?.comment ?? null
    return {
      ...base,
      author: ai ? ('ai' as const) : entry?.authorKind === 'admin' ? ('admin' as const) : ('teacher' as const),
      ...(review ? { authorName: review.reviewerName } : {}),
      ...(review ? { verdict: writtenReviewVerdict(review.verdict, ai ? 'ai' : 'human') } : {}),
      ...(text?.trim() ? { text } : {}),
      ...(review && review.annotations.length > 0
        ? { media: <ReviewAnnotations review={review} thread={thread} /> }
        : {}),
      ...(review
        ? {
            footer: (
              <ReviewReactions
                error={reactionError?.reviewId === review.reviewId ? reactionError.message : null}
                now={now}
                onReaction={onReaction}
                pending={pendingReactionReviewId === review.reviewId}
                review={review}
              />
            ),
          }
        : {}),
    }
  })
}

export function StudentWrittenSubmission({
  problemId,
  problemType,
  conditionRevisionId,
  configVersion,
  closed = false,
}: StudentWrittenSubmissionProps) {
  const authentication = useAuthentication()
  const principal =
    authentication.state.status === 'authenticated' ||
    authentication.state.status === 'offline-unverified'
      ? authentication.state.principal
      : null
  if (!principal || principal.audience !== 'student') {
    throw new Error('Written submission requires an authenticated Student principal')
  }
  const ownerId = principal.accountId
  const database = useOfflineDatabase()
  const descriptor = useMemo<WrittenDraftDescriptor>(
    () => ({ ownerId, problemId, conditionRevisionId, configVersion }),
    [conditionRevisionId, configVersion, ownerId, problemId],
  )
  const client = useMemo(
    () =>
      createWrittenSubmissionClient(authentication.client.runtime, {
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
  const draftStore = useMemo(() => {
    try {
      return {
        value: createWrittenSubmissionDraftStore(
          { audience: 'student', instance: authentication.client.runtime.instance },
          window.localStorage,
          database,
        ),
        error: null,
      }
    } catch (error) {
      return { value: null, error }
    }
  }, [authentication.client.runtime.instance, database])
  const outbox = useMemo(
    () =>
      draftStore.value ? createWrittenSubmissionOutbox(database, ownerId, draftStore.value) : null,
    [database, draftStore.value, ownerId],
  )
  const principalScope = useMemo(
    () => ({ audience: 'student' as const, accountId: ownerId }),
    [ownerId],
  )
  const threadQuery = useWrittenThreadQuery(client, principalScope, problemId)
  const studentReactionMutation = useWrittenStudentReactionMutation(
    client,
    principalScope,
    problemId,
  )
  const refetchThread = threadQuery.refetch
  const inputRef = useRef<HTMLInputElement>(null)
  const deliveryActive = useRef(false)
  const photoProcessing = useRef(new Map<string, AbortController>())
  const [hydrated, setHydrated] = useState(false)
  const [text, setText] = useState('')
  const [photos, setPhotos] = useState<ResolvedWrittenDraftPhoto[]>([])
  const [pendingPhotos, setPendingPhotos] = useState<PendingPhoto[]>([])
  const [queueItem, setQueueItem] = useState<WrittenSubmissionOutboxItem | null>(null)
  const [replacementTarget, setReplacementTarget] = useState<WrittenDraftReplacementTarget | null>(
    null,
  )
  const [replacementLoading, setReplacementLoading] = useState(false)
  const [storageError, setStorageError] = useState<unknown>(draftStore.error)
  const [sendError, setSendError] = useState<string | null>(null)
  const [studentReactionError, setStudentReactionError] = useState<{
    reviewId: string
    message: string
  } | null>(null)
  const [online, setOnline] = useState(() => navigator.onLine)
  const [mountedAt] = useState(() => Date.now())
  const previewUrls = usePhotoPreviewUrls(photos)

  const changeStudentReaction = async (
    reviewId: string,
    reactionId: 0 | 1 | 2 | null,
    expectedVersion: number,
  ) => {
    setStudentReactionError(null)
    try {
      await studentReactionMutation.mutateAsync({ reviewId, reactionId, expectedVersion })
    } catch (error) {
      authentication.handleApiError(error)
      setStudentReactionError({
        reviewId,
        message:
          error instanceof ApiResponseError
            ? error.message
            : 'Не удалось сохранить реакцию. Обновите проверку и попробуйте ещё раз.',
      })
      await refetchThread().catch(() => undefined)
    }
  }

  const reloadDraft = useCallback(async () => {
    if (!draftStore.value) return
    const loaded = await draftStore.value.load(descriptor)
    setText(loaded.compatible?.text ?? '')
    setPhotos(loaded.compatible?.photos ?? [])
    setReplacementTarget(loaded.compatible?.replacementTarget ?? null)
    setStorageError(null)
  }, [descriptor, draftStore.value])

  useEffect(() => {
    let active = true
    if (!draftStore.value || !outbox) {
      queueMicrotask(() => {
        if (active) setHydrated(true)
      })
      return () => {
        active = false
      }
    }
    void Promise.all([draftStore.value.load(descriptor), outbox.list()]).then(
      async ([loaded, items]) => {
        if (!active) return
        const item = relevantItem(items, descriptor)
        setText(loaded.compatible?.text ?? '')
        setPhotos(loaded.compatible?.photos ?? [])
        setReplacementTarget(loaded.compatible?.replacementTarget ?? null)
        setQueueItem(item)
        setStorageError(null)
        setHydrated(true)
        if (item?.status === 'synced') {
          await outbox.acknowledge(item.id)
          if (active) {
            setText('')
            setPhotos([])
            setReplacementTarget(null)
            setQueueItem(null)
            void refetchThread()
          }
        }
      },
      (error) => {
        if (active) {
          setStorageError(error)
          setHydrated(true)
        }
      },
    )
    return () => {
      active = false
    }
  }, [descriptor, draftStore.value, outbox, refetchThread])

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])

  useEffect(
    () => () => {
      for (const controller of photoProcessing.current.values()) controller.abort()
      photoProcessing.current.clear()
    },
    [descriptor],
  )

  const deliver = useCallback(async () => {
    if (!outbox || deliveryActive.current) return
    deliveryActive.current = true
    setSendError(null)
    let result: Awaited<ReturnType<typeof outbox.deliverNext>>
    try {
      result = await outbox.deliverNext(client)
    } catch (error) {
      setSendError(deliveryMessage(error))
      return
    } finally {
      // Release the single-flight guard before publishing a retrying queue
      // item. Its effect may run immediately; keeping the guard until after
      // setQueueItem would lose that reconnect retry until another event.
      deliveryActive.current = false
    }
    if (result.state === 'idle') return
    if (
      result.item.payload.descriptor.problemId !== descriptor.problemId ||
      result.item.payload.descriptor.conditionRevisionId !== descriptor.conditionRevisionId ||
      result.item.payload.descriptor.configVersion !== descriptor.configVersion
    ) {
      return
    }
    setQueueItem(result.item)
    if (result.state !== 'synced') {
      setSendError(deliveryMessage(result.error))
      return
    }
    await outbox.acknowledge(result.item.id)
    setQueueItem(null)
    setText('')
    setPhotos([])
    setReplacementTarget(null)
    await refetchThread()
    announceSafePwaUpdateMoment()
  }, [client, descriptor, outbox, refetchThread])

  useEffect(() => {
    if (online && queueItem && ['queued', 'retrying'].includes(queueItem.status)) {
      const delay =
        queueItem.status === 'queued'
          ? 0
          : Math.min(30_000, 1_000 * 2 ** Math.min(queueItem.attempts, 5))
      const timeout = window.setTimeout(() => void deliver(), delay)
      return () => window.clearTimeout(timeout)
    }
    return undefined
  }, [deliver, online, queueItem])

  if (!hydrated) {
    return (
      <Card aria-label="Загрузка письменного решения" className="mt-5">
        <CardContent className="space-y-3 pt-5">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    )
  }

  const chatMessages = writtenChatMessages({
    thread: threadQuery.data?.thread ?? null,
    now: mountedAt,
    onReaction: (reviewId, reactionId, expectedVersion) =>
      void changeStudentReaction(reviewId, reactionId, expectedVersion),
    pendingReactionReviewId: studentReactionMutation.isPending
      ? (studentReactionMutation.variables?.reviewId ?? null)
      : null,
    reactionError: studentReactionError,
  })

  if (closed) {
    return (
      <section aria-label="Отправленные решения" className="mt-4 space-y-3">
        <TaskChat
          emptyLabel="Приём решений завершён, отправленных решений нет."
          messages={chatMessages}
        />
      </section>
    )
  }

  if (!draftStore.value || !outbox) {
    return (
      <Alert className="mt-5" role="alert" tone="danger">
        <TriangleAlert aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Нельзя надёжно сохранить решение</AlertTitle>
          <AlertDescription>
            Браузер не разрешил локальное хранение. Мы не открываем редактор, чтобы работа не
            потерялась при перезагрузке.
          </AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  const saveText = (value: string) => {
    setText(value)
    try {
      draftStore.value.saveText(descriptor, value)
      setStorageError(null)
    } catch (error) {
      setStorageError(error)
    }
  }

  const recordPaste = (characterCount: number) => {
    try {
      draftStore.value.recordPaste(descriptor, characterCount)
      setStorageError(null)
    } catch (error) {
      setStorageError(error)
    }
  }

  const selectPhotos = async (files: FileList | null) => {
    if (!files) return
    const selected = [...files].slice(0, Math.max(0, 10 - photos.length - pendingPhotos.length))
    for (const file of selected) {
      const id = crypto.randomUUID()
      const controller = new AbortController()
      photoProcessing.current.set(id, controller)
      setPendingPhotos((current) => [...current, { id, name: file.name, status: 'processing' }])
      try {
        const result = await compressWrittenSubmissionImage(file, { signal: controller.signal })
        await draftStore.value.addPhoto(descriptor, {
          id,
          fileName: result.status === 'ready' ? result.fileName : file.name,
          blob: result.status === 'ready' ? result.blob : result.source,
          width: result.status === 'ready' ? result.width : null,
          height: result.status === 'ready' ? result.height : null,
          processing: result.status === 'ready' ? 'client-webp' : 'server-fallback-source',
        })
        setPendingPhotos((current) => current.filter((photo) => photo.id !== id))
        await reloadDraft()
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          setPendingPhotos((current) => current.filter((photo) => photo.id !== id))
          continue
        }
        setPendingPhotos((current) =>
          current.map((photo) =>
            photo.id === id
              ? {
                  ...photo,
                  status: 'failed',
                  error: error instanceof Error ? error.message : 'Не удалось сохранить фото',
                }
              : photo,
          ),
        )
      } finally {
        photoProcessing.current.delete(id)
      }
    }
    if (inputRef.current) inputRef.current.value = ''
  }

  const move = (photoId: string, offset: -1 | 1) => {
    const index = photos.findIndex((photo) => photo.id === photoId)
    const target = index + offset
    if (index < 0 || target < 0 || target >= photos.length) return
    const reordered = [...photos]
    const [photo] = reordered.splice(index, 1)
    if (!photo) return
    reordered.splice(target, 0, photo)
    try {
      draftStore.value.reorderPhotos(
        descriptor,
        reordered.map(({ id }) => id),
      )
      setPhotos(reordered)
      setStorageError(null)
    } catch (error) {
      setStorageError(error)
    }
  }

  const remove = async (photoId: string) => {
    if (!window.confirm('Удалить эту страницу из решения?')) return
    if (pendingPhotos.some((photo) => photo.id === photoId)) {
      photoProcessing.current.get(photoId)?.abort()
      setPendingPhotos((current) => current.filter((photo) => photo.id !== photoId))
      return
    }
    try {
      await draftStore.value.removePhoto(descriptor, photoId)
      await reloadDraft()
    } catch (error) {
      setStorageError(error)
    }
  }

  const submit = async () => {
    setSendError(null)
    try {
      if (
        replacementTarget &&
        !window.confirm(
          'Заменить ранее отправленное решение этой версией? Прежняя версия исчезнет из очереди проверки.',
        )
      ) {
        return
      }
      const item = await outbox.enqueue(descriptor)
      setQueueItem(item)
      if (navigator.onLine) await deliver()
    } catch (error) {
      setSendError(deliveryMessage(error))
    }
  }

  const attachmentStatus = (photo: ResolvedWrittenDraftPhoto): AttachmentView['status'] => {
    const queuedPhoto = queueItem?.payload.photos.find(
      (candidate) => candidate.localPhotoId === photo.id,
    )
    if (queuedPhoto?.serverAttachmentId) return 'ready'
    if (queueItem?.status === 'sending') return 'uploading'
    if (queueItem && ['queued', 'retrying'].includes(queueItem.status)) return 'queued'
    return 'ready'
  }
  const attachments: AttachmentView[] = [
    ...photos.map((photo) => ({
      id: photo.id,
      name: photo.fileName,
      sizeLabel: formatBytes(photo.byteSize),
      previewUrl: previewUrls.get(photo.id),
      status: attachmentStatus(photo),
    })),
    ...pendingPhotos.map((photo) => ({
      id: photo.id,
      name: photo.name,
      status: photo.status,
      ...(photo.error ? { error: photo.error } : {}),
    })),
  ]
  const queued = queueItem !== null && ['queued', 'retrying', 'sending'].includes(queueItem.status)
  const totalBytes = photos.reduce((sum, photo) => sum + photo.byteSize, 0)
  const thread = threadQuery.data?.thread ?? null
  const replaceableEntry = replaceableWrittenEntry(thread)

  const beginReplacement = async () => {
    if (!replaceableEntry || queued || replacementLoading) return
    if (
      !window.confirm(
        'Подготовить замену отправленного решения? До отправки прежняя версия останется без изменений.',
      )
    ) {
      return
    }
    const target = {
      entryId: replaceableEntry.entryId,
      entryVersion: replaceableEntry.version,
    }
    try {
      draftStore.value.saveReplacementTarget(descriptor, target)
      setReplacementTarget(target)
      if (text.trim() || photos.length > 0) return
      setReplacementLoading(true)
      draftStore.value.saveText(descriptor, replaceableEntry.text ?? '')
      for (const [index, attachment] of replaceableEntry.attachments.entries()) {
        const blob = await client.attachmentMedia(replaceableEntry.entryId, attachment.attachmentId)
        await draftStore.value.addPhoto(descriptor, {
          fileName: `Страница ${index + 1}.webp`,
          blob,
          width: attachment.width,
          height: attachment.height,
          processing: 'client-webp',
        })
      }
      await reloadDraft()
    } catch {
      setSendError(
        'Не удалось полностью скопировать прежнюю версию. Уже сохранённые страницы не потеряны; проверьте черновик и добавьте недостающие.',
      )
      await reloadDraft().catch(() => undefined)
    } finally {
      setReplacementLoading(false)
    }
  }

  const cancelReplacement = () => {
    if (
      !window.confirm(
        'Отменить режим замены? Текст и фотографии останутся в черновике и смогут отправиться новым сообщением.',
      )
    ) {
      return
    }
    try {
      draftStore.value.saveReplacementTarget(descriptor, null)
      setReplacementTarget(null)
      setStorageError(null)
    } catch (error) {
      setStorageError(error)
    }
  }

  // While an answer is on its way it already reads as a sent message, so the
  // composer steps aside instead of showing the same text twice.
  const queuedMessage: ChatMessageView | null =
    queued && queueItem
      ? {
          id: `queued:${queueItem.id}`,
          author: 'student',
          own: true,
          at: chatTime(queueItem.payload.clientCreatedAt),
          dateLabel: chatDate(queueItem.payload.clientCreatedAt),
          ...(queueItem.payload.text?.trim() ? { text: queueItem.payload.text } : {}),
          ...(photos.length > 0
            ? {
                media: (
                  <ol className="flex flex-wrap gap-1.5">
                    {photos.map((photo, index) => (
                      <li key={photo.id}>
                        <img
                          alt={`Страница ${index + 1}`}
                          className="max-h-32 rounded border border-border bg-surface-sunken"
                          src={previewUrls.get(photo.id)}
                        />
                      </li>
                    ))}
                  </ol>
                ),
              }
            : {}),
          delivery: queueItem.status === 'sending' ? 'sending' : 'queued',
        }
      : null

  const editableMessages = chatMessages.map((message) =>
    replaceableEntry && message.id === `entry:${replaceableEntry.entryId}` && !replacementTarget
      ? {
          ...message,
          actions: (
            <Button
              disabled={replacementLoading}
              onClick={() => void beginReplacement()}
              size="sm"
              variant="ghost"
            >
              <Pencil aria-hidden="true" />
              Изменить
            </Button>
          ),
        }
      : message,
  )
  const messages = queuedMessage ? [...editableMessages, queuedMessage] : editableMessages
  const composerEmpty = text.trim() === '' && attachments.length === 0

  return (
    <section
      aria-label={replacementTarget ? 'Изменить решение' : 'Сдать решение'}
      className="mt-4 space-y-3 border-t border-border pt-4"
    >
      <TaskChat
        emptyLabel="Здесь появится переписка по задаче: ваше решение и ответ проверяющего."
        messages={messages}
      />

      {storageError ? (
        <Alert role="alert" tone="danger">
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Последнее изменение не сохранено</AlertTitle>
            <AlertDescription>
              Не закрывайте страницу. Освободите место в браузере и повторите изменение.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {sendError ? (
        <Alert role="alert" tone="danger">
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Отправка не завершена</AlertTitle>
            <AlertDescription>{sendError}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      <input
        accept="image/*,.heic,.heif"
        className="sr-only"
        multiple
        onChange={(event) => void selectPhotos(event.currentTarget.files)}
        ref={inputRef}
        type="file"
      />

      {queued ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-subtle px-3 py-2 font-sans">
          <CloudOff aria-hidden="true" className="size-4 text-muted-foreground" />
          <p className="min-w-0 flex-1 text-small text-muted-foreground">
            {queueItem?.status === 'sending'
              ? 'Отправляем решение…'
              : 'Решение в очереди — отправка продолжится, когда появится связь.'}
          </p>
          {online && queueItem?.status !== 'sending' ? (
            <Button onClick={() => void deliver()} size="sm" variant="outline">
              Повторить сейчас
            </Button>
          ) : null}
        </div>
      ) : (
        <>
          {replacementTarget ? (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-subtle px-3 py-2 font-sans">
              <Pencil aria-hidden="true" className="size-4 text-muted-foreground" />
              <p className="min-w-0 flex-1 text-small text-muted-foreground">
                {replacementLoading
                  ? 'Копируем прежнее решение…'
                  : 'Изменяете отправленное решение — оно заменится одной операцией.'}
              </p>
              {!replacementLoading ? (
                <Button onClick={cancelReplacement} size="sm" variant="ghost">
                  Отменить
                </Button>
              ) : null}
            </div>
          ) : null}
          <ChatComposer
            attachments={attachments}
            attachDisabled={replacementLoading || attachments.length >= 10}
            attachmentsDisabled={replacementLoading}
            hint={
              <span className="flex flex-wrap items-center gap-x-3">
                <span>
                  Фотографии: {attachments.length} из 10
                  {photos.length > 0 ? ` · ${formatBytes(totalBytes)}` : ''}
                </span>
                {problemType === 'oral' ? (
                  <span>Устную задачу можно сдать в конференции или письменно здесь.</span>
                ) : null}
                {!online ? <span>Нет сети — отправим, когда связь вернётся.</span> : null}
              </span>
            }
            onAttach={() => inputRef.current?.click()}
            onMoveAttachmentDown={(id) => move(id, 1)}
            onMoveAttachmentUp={(id) => move(id, -1)}
            onRemoveAttachment={(id) => void remove(id)}
            onSend={() => void submit()}
            sendDisabled={composerEmpty || replacementLoading}
            sending={replacementLoading}
          >
            <Textarea
              aria-label="Ваше решение"
              className="field-sizing-content max-h-56 min-h-11 py-2 text-base sm:text-[1.0625rem]"
              disabled={replacementLoading}
              onChange={(event) => saveText(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault()
                  if (!composerEmpty && !replacementLoading) void submit()
                }
              }}
              onPaste={(event) => {
                const characterCount = event.clipboardData.getData('text').length
                if (characterCount > 0) recordPaste(characterCount)
              }}
              placeholder="Решение или пояснение. Формулы можно приложить фотографией."
              value={text}
            />
          </ChatComposer>
        </>
      )}
    </section>
  )
}

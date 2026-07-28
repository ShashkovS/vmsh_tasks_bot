import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, CloudOff, Pencil, TriangleAlert } from 'lucide-react'

import {
  createWrittenSubmissionClient,
  useAuthentication,
  useWrittenThreadQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type StudentProblemType } from '@vmsh/contracts'
import {
  createWrittenSubmissionDraftStore,
  createWrittenSubmissionOutbox,
  useOfflineDatabase,
  type ResolvedWrittenDraftPhoto,
  type WrittenDraftDescriptor,
  type WrittenDraftReplacementTarget,
  type WrittenSubmissionOutboxItem,
} from '@vmsh/offline'
import { SubmissionComposer, WrittenReviewHistory, type AttachmentView } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@vmsh/ui'

import { compressWrittenSubmissionImage } from './image-compression'

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

export function StudentWrittenSubmission({
  problemId,
  problemType,
  conditionRevisionId,
  configVersion,
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
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [online, setOnline] = useState(() => navigator.onLine)
  const previewUrls = usePhotoPreviewUrls(photos)

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
          setSent(true)
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
    setSent(true)
    await outbox.acknowledge(result.item.id)
    setQueueItem(null)
    setText('')
    setPhotos([])
    setReplacementTarget(null)
    await refetchThread()
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
    setSent(false)
    try {
      draftStore.value.saveText(descriptor, value)
      setSavedAt(new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }))
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
        setSent(false)
        await reloadDraft()
        setSavedAt(new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }))
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
      setSent(false)
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
      setSent(false)
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
  const threadStatus = thread?.status ?? null
  const replaceableEntry = [...(thread?.entries ?? [])]
    .reverse()
    .find(
      (entry) =>
        entry.authorKind === 'student' &&
        entry.entryKind === 'submission' &&
        entry.state === 'submitted',
    )

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
      setSent(false)
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
      setSavedAt(new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }))
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

  return (
    <Card className="mt-5">
      <CardHeader>
        <CardTitle>{replacementTarget ? 'Изменить решение' : 'Сдать решение'}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {thread?.reviews.length ? (
          <WrittenReviewHistory entries={thread.entries} reviews={thread.reviews} />
        ) : null}
        {replaceableEntry && !replacementTarget && !queued ? (
          <Button
            disabled={replacementLoading}
            onClick={() => void beginReplacement()}
            size="sm"
            variant="outline"
          >
            <Pencil aria-hidden="true" />
            Изменить отправленное решение
          </Button>
        ) : null}
        {replacementTarget ? (
          <Alert tone="info">
            <Pencil aria-hidden="true" />
            <AlertContent>
              <AlertTitle>
                {replacementLoading ? 'Копируем прежнее решение…' : 'Готовится замена'}
              </AlertTitle>
              <AlertDescription>
                Прежнее решение останется в очереди до полной отправки этой версии. После
                подтверждения текст и фотографии заменятся одной операцией.
              </AlertDescription>
              {!queued && !replacementLoading ? (
                <Button className="mt-2" onClick={cancelReplacement} size="sm" variant="ghost">
                  Отменить замену
                </Button>
              ) : null}
            </AlertContent>
          </Alert>
        ) : null}
        {threadStatus === 'awaiting_review' ? (
          <Alert tone="info">
            <AlertContent>
              <AlertTitle>Предыдущее сообщение ждёт проверки</AlertTitle>
              <AlertDescription>
                Можно дописать пояснение или отправить новое решение — оно добавится в тот же тред.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {sent ? (
          <Alert tone="success">
            <CheckCircle2 aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Решение отправлено</AlertTitle>
              <AlertDescription>
                Оно сохранено на сервере и появилось в истории задачи.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
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
        {queueItem && ['queued', 'retrying'].includes(queueItem.status) ? (
          <Alert tone="warning">
            <CloudOff aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Решение сохранено в очереди</AlertTitle>
              <AlertDescription>
                Отправка продолжится с последнего подтверждённого шага, когда появится связь.
              </AlertDescription>
              {online ? (
                <Button className="mt-2" onClick={() => void deliver()} size="sm" variant="outline">
                  Повторить сейчас
                </Button>
              ) : null}
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
        <SubmissionComposer
          attachments={attachments}
          {...(savedAt ? { draftSavedAt: savedAt } : {})}
          maxPhotos={10}
          offline={!online}
          onAddPhotos={() => inputRef.current?.click()}
          onMoveDown={(id) => move(id, 1)}
          onMoveUp={(id) => move(id, -1)}
          onRemove={(id) => void remove(id)}
          onSubmit={() => void submit()}
          onTextChange={saveText}
          queued={queued}
          submitting={queueItem?.status === 'sending' || replacementLoading}
          taskType={problemType}
          text={text}
          {...(photos.length > 0 ? { totalSizeLabel: formatBytes(totalBytes) } : {})}
        />
      </CardContent>
    </Card>
  )
}

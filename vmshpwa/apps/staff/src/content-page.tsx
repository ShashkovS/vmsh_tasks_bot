import { AlertTriangle, CheckCircle2, FileCode2, RefreshCw, Send, Upload } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageLayout, PageStatePanel, useAuthentication } from '@vmsh/app-shell'
import {
  SemanticMathDocument,
  createContentApiClient,
  type ContentApiClient,
  type PublicationSlotVersion,
  type VersionedContentResource,
  useStaffContentHistoryQuery,
} from '@vmsh/content'
import {
  ApiResponseError,
  contentAssetsMissingDetailsSchema,
  localPublicationTimeSchema,
  staffContentRevisionSchema,
  type BusinessTimezone,
  type ContentMaterialKind,
  type ContentPublication,
  type ContentPublicationHistoryItem,
  type StaffContentMaterialHistory,
  type StaffContentRevision,
  type StaffPdfContentPreview,
  type WebContentDocument,
} from '@vmsh/contracts'
import { LatexUpload } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@vmsh/ui'

import { RevisionAssetsRecovery } from './revision-assets-recovery'
import { ProblemReviewWorkflow } from './problem-review-workflow'

const materialOrder: ContentMaterialKind[] = ['condition', 'hint', 'solution']
const materialLabels: Record<ContentMaterialKind, string> = {
  condition: 'Условие',
  hint: 'Подсказка',
  solution: 'Решение',
}

type VersionedRevision = VersionedContentResource<StaffContentRevision>
type VersionedPublication = VersionedContentResource<ContentPublication>

interface PublicationView {
  publicationId: string
  revisionId: string
  version: number
  scheduledAt: string | null
  publishedAt: string | null
}

interface VersionedPublicationView {
  data: PublicationView
  etag: VersionedPublication['etag']
}

interface MaterialWorkflowState {
  file: File | undefined
  phase: 'idle' | 'processing' | 'ready' | 'invalid' | 'error'
  revisions: VersionedRevision[]
  invalidRevision: StaffContentRevision | undefined
  webDocument: WebContentDocument | undefined
  telegramHtml: string | undefined
  pdfPreview: StaffPdfContentPreview | undefined
  pdfCheckedRevisionId: string | undefined
  pdfErrorMessage: string | undefined
  previewRevisionId: string | undefined
  previewLoading: boolean
  selectedRevisionId: string | undefined
  reviewReadyRevisionId: string | undefined
  rollbackRevisionId: string | undefined
  currentPublication: VersionedPublicationView | undefined
  scheduledPublication: VersionedPublicationView | undefined
  scheduleAt: string
  mutationPending: boolean
  errorMessage: string | undefined
}

type ConfirmationAction = 'publish' | 'schedule' | 'rollback' | 'hide'

function publicationView(
  resource:
    VersionedPublication | (ContentPublicationHistoryItem & { etag: VersionedPublication['etag'] }),
): VersionedPublicationView {
  const publication = 'data' in resource ? resource.data : resource
  return {
    data: {
      publicationId: publication.publicationId,
      revisionId: publication.revisionId,
      version: publication.version,
      scheduledAt: publication.scheduledAt,
      publishedAt: publication.publishedAt,
    },
    etag: resource.etag,
  }
}

function initialMaterialState(history?: StaffContentMaterialHistory): MaterialWorkflowState {
  const revisions = revisionsFromHistory(history)
  const readyRevisions = revisions.filter((revision) => revision.data.status === 'ready')
  const selectedRevisionId = readyRevisions.at(-1)?.data.revisionId
  const currentRevisionId = history?.currentPublished?.revisionId
  const rollbackRevisionId = [...readyRevisions]
    .reverse()
    .find((revision) => revision.data.revisionId !== currentRevisionId)?.data.revisionId
  return {
    file: undefined,
    phase: 'idle',
    revisions,
    invalidRevision: undefined,
    webDocument: undefined,
    telegramHtml: undefined,
    pdfPreview: undefined,
    pdfCheckedRevisionId: undefined,
    pdfErrorMessage: undefined,
    previewRevisionId: undefined,
    previewLoading: false,
    selectedRevisionId,
    reviewReadyRevisionId: undefined,
    rollbackRevisionId,
    currentPublication: history?.currentPublished
      ? publicationView(history.currentPublished)
      : undefined,
    scheduledPublication: history?.currentScheduled
      ? publicationView(history.currentScheduled)
      : undefined,
    scheduleAt: '',
    mutationPending: false,
    errorMessage: undefined,
  }
}

function revisionsFromHistory(history?: StaffContentMaterialHistory): VersionedRevision[] {
  return (history?.revisions ?? [])
    .map((revision) => {
      const { etag, ...data } = revision
      return { data, etag }
    })
    .sort((left, right) => left.data.revisionNumber - right.data.revisionNumber)
}

function publicationSlot(
  resource: VersionedPublicationView | undefined,
): PublicationSlotVersion | undefined {
  if (!resource) return undefined
  return {
    publicationId: resource.data.publicationId,
    version: resource.data.version,
    etag: resource.etag,
  }
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось выполнить действие'
}

async function optionalPdfPreview(
  client: ContentApiClient,
  revisionId: string,
): Promise<{ preview?: StaffPdfContentPreview; error?: string }> {
  try {
    const preview = await client.preview(revisionId, 'pdf')
    if (preview.kind !== 'pdf') throw new Error('Сервер вернул несовместимый PDF preview')
    return { preview }
  } catch (error) {
    if (error instanceof ApiResponseError && error.status === 404) return {}
    return { error: errorMessage(error) }
  }
}

function materialHistoryFor(
  materials: StaffContentMaterialHistory[],
  kind: ContentMaterialKind,
): StaffContentMaterialHistory {
  const material = materials.find((candidate) => candidate.kind === kind)
  if (!material) throw new Error(`Content history has no ${kind} slot`)
  return material
}

function isRecoverableRevision(revision: StaffContentRevision, now = Date.now()): boolean {
  if (revision.status === 'uploaded') return true
  if (revision.status !== 'compiling') return false
  if (revision.compileLeaseExpiresAt === null) return true
  return Date.parse(revision.compileLeaseExpiresAt) <= now
}

function formatInBusinessTimezone(instant: string, timezone: BusinessTimezone): string {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: timezone,
  }).format(new Date(instant))
}

function MaterialWorkflowCard({
  client,
  groupLessonId,
  history,
  kind,
  businessTimezone,
  onConflict,
}: {
  client: ContentApiClient
  groupLessonId: string
  history: StaffContentMaterialHistory
  kind: ContentMaterialKind
  businessTimezone: BusinessTimezone
  onConflict: () => Promise<unknown>
}) {
  const [state, setState] = useState<MaterialWorkflowState>(() => initialMaterialState(history))
  const [confirmation, setConfirmation] = useState<ConfirmationAction | null>(null)
  const latest = state.revisions.at(-1)
  const readyRevisions = state.revisions.filter(
    (revision) => revision.data.status === 'ready' && revision.data.missingAssets.length === 0,
  )
  const selectedRevision = readyRevisions.find(
    (revision) => revision.data.revisionId === state.selectedRevisionId,
  )
  const rollbackRevision = readyRevisions.find(
    (revision) => revision.data.revisionId === state.rollbackRevisionId,
  )
  const readyForPublication =
    selectedRevision !== undefined &&
    state.reviewReadyRevisionId === selectedRevision.data.revisionId
  const recoverableRevisions = state.revisions.filter((revision) =>
    isRecoverableRevision(revision.data),
  )
  const activeCompilations = state.revisions.filter(
    (revision) => revision.data.status === 'compiling' && !isRecoverableRevision(revision.data),
  )
  const inputId = `latex-source-${kind}`
  const scheduleId = `publication-schedule-${kind}`

  const patchState = (patch: Partial<MaterialWorkflowState>) =>
    setState((current) => ({ ...current, ...patch }))

  const handleReviewReady = useCallback((revisionId: string, ready: boolean) => {
    setState((current) => {
      const nextRevisionId = ready ? revisionId : undefined
      if (
        current.selectedRevisionId !== revisionId ||
        current.reviewReadyRevisionId === nextRevisionId
      ) {
        return current
      }
      return { ...current, reviewReadyRevisionId: nextRevisionId }
    })
  }, [])

  useEffect(() => {
    const serverRevisions = revisionsFromHistory(history)
    setState((current) => {
      const revisionsById = new Map(
        [...current.revisions, ...serverRevisions].map((revision) => [
          revision.data.revisionId,
          revision,
        ]),
      )
      const revisions = [...revisionsById.values()].sort(
        (left, right) => left.data.revisionNumber - right.data.revisionNumber,
      )
      const ready = revisions.filter((revision) => revision.data.status === 'ready')
      const currentRevisionId = history.currentPublished?.revisionId
      const selectedRevisionId = ready.some(
        (revision) => revision.data.revisionId === current.selectedRevisionId,
      )
        ? current.selectedRevisionId
        : ready.at(-1)?.data.revisionId
      const rollbackRevisionId = ready.some(
        (revision) => revision.data.revisionId === current.rollbackRevisionId,
      )
        ? current.rollbackRevisionId
        : [...ready].reverse().find((revision) => revision.data.revisionId !== currentRevisionId)
            ?.data.revisionId
      return {
        ...current,
        revisions,
        selectedRevisionId,
        reviewReadyRevisionId:
          selectedRevisionId === current.selectedRevisionId
            ? current.reviewReadyRevisionId
            : undefined,
        rollbackRevisionId,
        currentPublication: history.currentPublished
          ? publicationView(history.currentPublished)
          : undefined,
        scheduledPublication: history.currentScheduled
          ? publicationView(history.currentScheduled)
          : undefined,
      }
    })
  }, [history])

  const handleMutationError = (error: unknown) => {
    if (error instanceof ApiResponseError && error.status === 409) {
      patchState({
        errorMessage: 'Материал уже изменён. Обновляем версии и публикации…',
      })
      void onConflict()
      return
    }
    patchState({ errorMessage: errorMessage(error) })
  }

  const inspectCompiledRevision = async (revisionId: string) => {
    const [inspected, webPreview, telegramPreview, pdf] = await Promise.all([
      client.diagnostics(revisionId),
      client.preview(revisionId, 'web'),
      client.preview(revisionId, 'telegram'),
      optionalPdfPreview(client, revisionId),
    ])
    if (webPreview.kind !== 'web' || telegramPreview.kind !== 'telegram') {
      throw new Error('Сервер вернул несовместимые preview')
    }
    setState((current) => ({
      ...current,
      phase: 'ready',
      revisions: [
        ...current.revisions.filter(
          (revision) => revision.data.revisionId !== inspected.data.revisionId,
        ),
        inspected,
      ].sort((left, right) => left.data.revisionNumber - right.data.revisionNumber),
      selectedRevisionId: inspected.data.revisionId,
      reviewReadyRevisionId: undefined,
      webDocument: webPreview.document,
      telegramHtml: telegramPreview.html,
      pdfPreview: pdf.preview,
      pdfCheckedRevisionId: inspected.data.revisionId,
      pdfErrorMessage: pdf.error,
      previewRevisionId: inspected.data.revisionId,
      previewLoading: false,
      invalidRevision: undefined,
      errorMessage: undefined,
    }))
  }

  const compileStoredRevision = async (revision: VersionedRevision) => {
    patchState({
      phase: 'processing',
      errorMessage: undefined,
      invalidRevision: undefined,
      webDocument: undefined,
      telegramHtml: undefined,
      pdfPreview: undefined,
      pdfCheckedRevisionId: undefined,
      pdfErrorMessage: undefined,
      previewRevisionId: undefined,
      previewLoading: false,
    })
    try {
      const compiled = await client.compileRevision(revision.data.revisionId, revision.etag)
      await inspectCompiledRevision(compiled.data.revisionId)
    } catch (error) {
      const missingAssets =
        error instanceof ApiResponseError && error.code === 'content_assets_missing'
          ? contentAssetsMissingDetailsSchema.safeParse(error.details)
          : undefined
      const invalidRevision = missingAssets?.success
        ? staffContentRevisionSchema.safeParse({
            ...revision.data,
            status: 'uploaded',
            missingAssets: missingAssets.data.missingAssets,
          })
        : error instanceof ApiResponseError
          ? staffContentRevisionSchema.safeParse(error.details)
          : undefined
      if (invalidRevision?.success) {
        setState((current) => ({
          ...current,
          phase: 'invalid',
          invalidRevision: invalidRevision.data,
          previewLoading: false,
          errorMessage: missingAssets?.success ? undefined : errorMessage(error),
        }))
      } else {
        patchState({ phase: 'error' })
        handleMutationError(error)
      }
    }
  }

  const compileSelectedFile = async () => {
    if (!state.file) return
    patchState({ phase: 'processing', errorMessage: undefined })
    try {
      const uploaded = await client.uploadSource({
        groupLessonId,
        kind,
        logicalFilename: state.file.name,
        source: state.file,
      })
      setState((current) => ({
        ...current,
        revisions: [...current.revisions, uploaded].sort(
          (left, right) => left.data.revisionNumber - right.data.revisionNumber,
        ),
      }))
      await compileStoredRevision(uploaded)
    } catch (error) {
      patchState({ phase: 'error' })
      handleMutationError(error)
    }
  }

  const loadSelectedPreviews = async () => {
    if (!selectedRevision) return
    patchState({ previewLoading: true, errorMessage: undefined })
    try {
      const [webPreview, telegramPreview, pdf] = await Promise.all([
        client.preview(selectedRevision.data.revisionId, 'web'),
        client.preview(selectedRevision.data.revisionId, 'telegram'),
        optionalPdfPreview(client, selectedRevision.data.revisionId),
      ])
      if (webPreview.kind !== 'web' || telegramPreview.kind !== 'telegram') {
        throw new Error('Сервер вернул несовместимые preview')
      }
      patchState({
        previewLoading: false,
        webDocument: webPreview.document,
        telegramHtml: telegramPreview.html,
        pdfPreview: pdf.preview,
        pdfCheckedRevisionId: selectedRevision.data.revisionId,
        pdfErrorMessage: pdf.error,
        previewRevisionId: selectedRevision.data.revisionId,
      })
    } catch (error) {
      patchState({ previewLoading: false })
      handleMutationError(error)
    }
  }

  const publish = async (mode: 'publish' | 'schedule') => {
    if (!selectedRevision || !readyForPublication) return
    const parsedLocalTime =
      mode === 'schedule' ? localPublicationTimeSchema.safeParse(state.scheduleAt) : undefined
    if (mode === 'schedule' && !parsedLocalTime?.success) {
      patchState({ errorMessage: 'Укажите корректные дату и время публикации.' })
      return
    }
    patchState({ errorMessage: undefined, mutationPending: true })
    try {
      const current =
        mode === 'publish'
          ? publicationSlot(state.currentPublication)
          : publicationSlot(state.scheduledPublication)
      const scheduled = publicationSlot(state.scheduledPublication)
      const published = await client.publish({
        groupLessonId,
        kind,
        revisionId: selectedRevision.data.revisionId,
        mode,
        ...(mode === 'schedule'
          ? {
              scheduledLocalTime: parsedLocalTime!.data,
              businessTimezone,
            }
          : {}),
        ...(current ? { current } : {}),
        ...(scheduled ? { scheduled } : {}),
      })
      setConfirmation(null)
      patchState(
        mode === 'publish'
          ? {
              currentPublication: publicationView(published),
              scheduledPublication: undefined,
              mutationPending: false,
            }
          : { scheduledPublication: publicationView(published), mutationPending: false },
      )
    } catch (error) {
      patchState({ mutationPending: false })
      handleMutationError(error)
    }
  }

  const rollback = async () => {
    const current = publicationSlot(state.currentPublication)
    if (!current || !rollbackRevision) return
    patchState({ errorMessage: undefined, mutationPending: true })
    try {
      const publication = await client.rollback(
        current,
        rollbackRevision.data.revisionId,
        publicationSlot(state.scheduledPublication),
      )
      patchState({
        currentPublication: publicationView(publication),
        scheduledPublication: undefined,
        selectedRevisionId: rollbackRevision.data.revisionId,
        mutationPending: false,
      })
    } catch (error) {
      patchState({ mutationPending: false })
      handleMutationError(error)
    }
  }

  const cancelSchedule = async () => {
    const current = publicationSlot(state.scheduledPublication)
    if (!current) return
    patchState({ errorMessage: undefined, mutationPending: true })
    try {
      await client.cancelScheduled(current)
      patchState({ scheduledPublication: undefined, mutationPending: false })
    } catch (error) {
      patchState({ mutationPending: false })
      handleMutationError(error)
    }
  }

  const hidePublication = async () => {
    const current = publicationSlot(state.currentPublication)
    if (!current) return
    patchState({ errorMessage: undefined, mutationPending: true })
    try {
      await client.hidePublished(current)
      setConfirmation(null)
      patchState({ currentPublication: undefined, mutationPending: false })
    } catch (error) {
      patchState({ mutationPending: false })
      handleMutationError(error)
    }
  }

  const visibleRevision = state.invalidRevision ?? selectedRevision?.data ?? latest?.data
  const diagnosticMessages = visibleRevision?.diagnostics.map(
    (diagnostic) =>
      `${diagnostic.span.start.line}:${diagnostic.span.start.column} · ${diagnostic.message}`,
  )

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle aria-level={2} role="heading">
            {materialLabels[kind]}
          </CardTitle>
          {state.currentPublication ? (
            <Badge variant="success">Опубликовано</Badge>
          ) : state.scheduledPublication ? (
            <Badge variant="info">По расписанию</Badge>
          ) : latest?.data.status === 'ready' ? (
            <Badge variant="neutral">Черновик готов</Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <div className="min-w-0 space-y-1">
            <Label htmlFor={inputId}>LaTeX-файл</Label>
            <Input
              accept=".tex,text/plain,application/x-tex"
              id={inputId}
              onChange={(event) => {
                const file = event.target.files?.[0]
                setState((current) => ({
                  ...current,
                  file,
                  phase: 'idle',
                  invalidRevision: undefined,
                  webDocument: undefined,
                  telegramHtml: undefined,
                  pdfPreview: undefined,
                  pdfCheckedRevisionId: undefined,
                  pdfErrorMessage: undefined,
                  previewRevisionId: undefined,
                  previewLoading: false,
                  errorMessage: undefined,
                }))
              }}
              type="file"
            />
          </div>
          <Button
            disabled={!state.file || state.phase === 'processing'}
            onClick={() => void compileSelectedFile()}
            size="sm"
          >
            <Upload aria-hidden="true" />
            {state.phase === 'processing' ? 'Проверяем…' : 'Загрузить и проверить'}
          </Button>
        </div>

        {state.file ? (
          <LatexUpload
            files={[
              {
                id: `${kind}-${state.file.name}`,
                name: state.file.name,
                status:
                  state.phase === 'processing'
                    ? 'processing'
                    : state.phase === 'invalid' || state.phase === 'error'
                      ? 'error'
                      : state.phase === 'ready'
                        ? 'done'
                        : 'queued',
                ...(diagnosticMessages?.length ? { diagnostics: diagnosticMessages } : {}),
              },
            ]}
          />
        ) : null}

        {recoverableRevisions.length || activeCompilations.length ? (
          <section
            aria-labelledby={`unfinished-revisions-${kind}`}
            className="space-y-2 rounded-md border border-border bg-surface-subtle p-3"
          >
            <h3 className="text-small font-medium" id={`unfinished-revisions-${kind}`}>
              Незавершённые загрузки
            </h3>
            <ul className="space-y-2">
              {recoverableRevisions.map((revision) => (
                <li
                  className="flex flex-wrap items-center justify-between gap-2 text-small"
                  key={revision.data.revisionId}
                >
                  <span>
                    Revision {revision.data.revisionNumber} · {revision.data.logicalFilename}
                    <span className="ml-1 text-muted-foreground">
                      {revision.data.status === 'uploaded'
                        ? 'загружена, но не проверена'
                        : 'проверка прервалась'}
                    </span>
                  </span>
                  <Button
                    aria-label={`Продолжить проверку revision ${revision.data.revisionNumber}`}
                    disabled={state.phase === 'processing'}
                    onClick={() => void compileStoredRevision(revision)}
                    size="xs"
                    variant="outline"
                  >
                    <RefreshCw aria-hidden="true" /> Продолжить проверку
                  </Button>
                </li>
              ))}
              {activeCompilations.map((revision) => (
                <li className="text-small text-muted-foreground" key={revision.data.revisionId}>
                  Revision {revision.data.revisionNumber} проверяется. Повтор станет доступен после
                  окончания lease.
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {readyRevisions.length > 1 ? (
          <div className="max-w-md space-y-1">
            <Label htmlFor={`ready-revision-${kind}`}>Revision для preview и публикации</Label>
            <Select
              onValueChange={(value) =>
                patchState({
                  selectedRevisionId: value as string,
                  reviewReadyRevisionId: undefined,
                  webDocument: undefined,
                  telegramHtml: undefined,
                  pdfPreview: undefined,
                  pdfCheckedRevisionId: undefined,
                  pdfErrorMessage: undefined,
                  previewRevisionId: undefined,
                })
              }
              value={state.selectedRevisionId}
            >
              <SelectTrigger className="w-full" id={`ready-revision-${kind}`}>
                <SelectValue>
                  {selectedRevision
                    ? `Revision ${selectedRevision.data.revisionNumber} · ${selectedRevision.data.logicalFilename}`
                    : 'Выберите revision'}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {[...readyRevisions].reverse().map((revision) => (
                  <SelectItem key={revision.data.revisionId} value={revision.data.revisionId}>
                    Revision {revision.data.revisionNumber} · {revision.data.logicalFilename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {!state.file && diagnosticMessages?.length ? (
          <Alert
            role="status"
            tone={
              visibleRevision?.diagnostics.some((item) => item.severity === 'error')
                ? 'danger'
                : 'warning'
            }
          >
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Диагностика revision {visibleRevision?.revisionNumber}</AlertTitle>
              <div className="mt-0.5 text-muted-foreground">
                <ul className="list-disc space-y-1 pl-5">
                  {diagnosticMessages.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </div>
            </AlertContent>
          </Alert>
        ) : null}

        {visibleRevision?.missingAssets.length ? (
          <RevisionAssetsRecovery
            client={client}
            key={visibleRevision.revisionId}
            onCompile={compileStoredRevision}
            revisionId={visibleRevision.revisionId}
          />
        ) : null}

        {selectedRevision && selectedRevision.data.missingAssets.length === 0 ? (
          <ProblemReviewWorkflow
            client={client}
            groupLessonId={groupLessonId}
            key={`${kind}:${selectedRevision.data.revisionId}`}
            kind={kind}
            onReadyChange={handleReviewReady}
            revisionId={selectedRevision.data.revisionId}
          />
        ) : null}

        {state.errorMessage ? (
          <Alert role="alert" tone="danger">
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Действие не выполнено</AlertTitle>
              <AlertDescription>{state.errorMessage}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}

        {selectedRevision &&
        (state.previewRevisionId !== selectedRevision.data.revisionId ||
          !state.webDocument ||
          !state.telegramHtml) ? (
          <Button
            disabled={state.previewLoading}
            onClick={() => void loadSelectedPreviews()}
            size="sm"
            variant="outline"
          >
            {state.previewLoading ? 'Загружаем preview…' : 'Показать PWA и Telegram preview'}
          </Button>
        ) : null}

        {state.webDocument &&
        state.telegramHtml &&
        state.previewRevisionId === selectedRevision?.data.revisionId ? (
          <section
            aria-label={`Preview: ${materialLabels[kind]}`}
            className="grid min-w-0 gap-3 lg:grid-cols-3 lg:items-start"
          >
            <div className="min-w-0 space-y-2">
              <h3 className="text-small font-medium">PWA</h3>
              <div className="rounded-md border border-border bg-surface p-3">
                <SemanticMathDocument document={state.webDocument} />
              </div>
            </div>
            <div className="min-w-0 space-y-2">
              <h3 className="text-small font-medium">Telegram Rich HTML</h3>
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-surface-sunken p-3 font-mono text-caption text-foreground">
                {state.telegramHtml}
              </pre>
            </div>
            <div className="min-w-0 space-y-2">
              <h3 className="text-small font-medium">PDF</h3>
              <div className="space-y-2 rounded-md border border-border bg-surface p-3 text-small">
                {state.pdfPreview && state.pdfCheckedRevisionId === state.previewRevisionId ? (
                  <>
                    <p className="text-muted-foreground">
                      Сохранённая производная ·{' '}
                      <span className="font-num">
                        {Math.ceil(state.pdfPreview.byteSize / 1024)} КБ
                      </span>
                    </p>
                    <a
                      className="inline-flex h-7 items-center rounded-md border border-border px-2.5 text-[0.8rem] font-medium text-primary outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-focus"
                      href={state.pdfPreview.src}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Открыть PDF
                    </a>
                  </>
                ) : state.pdfErrorMessage ? (
                  <p className="text-status-danger" role="alert">
                    PDF не удалось проверить: {state.pdfErrorMessage}
                  </p>
                ) : (
                  <p className="text-muted-foreground">
                    PDF-производная для этой revision пока не сохранена.
                  </p>
                )}
              </div>
            </div>
          </section>
        ) : null}

        {readyForPublication || state.currentPublication || state.scheduledPublication ? (
          <div className="space-y-3 rounded-md border border-border bg-surface-subtle p-3">
            <div className="flex flex-wrap items-center gap-2">
              {readyForPublication ? (
                <Button
                  disabled={state.mutationPending}
                  onClick={() => setConfirmation('publish')}
                  size="sm"
                >
                  <Send aria-hidden="true" /> Опубликовать сейчас
                </Button>
              ) : null}
              {state.currentPublication ? (
                <Button
                  disabled={state.mutationPending}
                  onClick={() => setConfirmation('hide')}
                  size="sm"
                  variant="outline"
                >
                  Скрыть опубликованное
                </Button>
              ) : null}
            </div>
            {readyForPublication ? (
              <div className="grid max-w-xl gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <div className="space-y-1">
                  <Label htmlFor={scheduleId}>Опубликовать по расписанию</Label>
                  <Input
                    id={scheduleId}
                    onChange={(event) => patchState({ scheduleAt: event.target.value })}
                    step="60"
                    type="datetime-local"
                    value={state.scheduleAt}
                  />
                  <p className="text-caption text-muted-foreground">
                    Время занятия: {businessTimezone}. Сервер проверит переходы летнего времени.
                  </p>
                </div>
                <Button
                  disabled={!state.scheduleAt || state.mutationPending}
                  onClick={() => {
                    if (localPublicationTimeSchema.safeParse(state.scheduleAt).success) {
                      setConfirmation('schedule')
                      patchState({ errorMessage: undefined })
                    } else {
                      patchState({ errorMessage: 'Укажите корректные дату и время публикации.' })
                    }
                  }}
                  size="sm"
                  variant="outline"
                >
                  Запланировать
                </Button>
              </div>
            ) : null}
            {state.currentPublication &&
            readyRevisions.some(
              (revision) => revision.data.revisionId !== state.currentPublication?.data.revisionId,
            ) ? (
              <div className="grid max-w-xl gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <div className="space-y-1">
                  <Label htmlFor={`rollback-revision-${kind}`}>Revision для отката</Label>
                  <Select
                    onValueChange={(value) => value && patchState({ rollbackRevisionId: value })}
                    value={state.rollbackRevisionId}
                  >
                    <SelectTrigger className="w-full" id={`rollback-revision-${kind}`}>
                      <SelectValue>
                        {rollbackRevision
                          ? `Revision ${rollbackRevision.data.revisionNumber} · ${rollbackRevision.data.logicalFilename}`
                          : 'Выберите revision'}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {[...readyRevisions]
                        .reverse()
                        .filter(
                          (revision) =>
                            revision.data.revisionId !== state.currentPublication?.data.revisionId,
                        )
                        .map((revision) => (
                          <SelectItem
                            key={revision.data.revisionId}
                            value={revision.data.revisionId}
                          >
                            Revision {revision.data.revisionNumber} ·{' '}
                            {revision.data.logicalFilename}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  disabled={!rollbackRevision || state.mutationPending}
                  onClick={() => setConfirmation('rollback')}
                  size="sm"
                  variant="outline"
                >
                  Откатить опубликованное
                </Button>
              </div>
            ) : null}
            {confirmation ? (
              <div
                aria-labelledby={`publication-confirmation-${kind}`}
                className="space-y-2 rounded-md border border-status-warning/40 bg-status-warning/10 p-3"
                role="group"
              >
                <p className="font-medium" id={`publication-confirmation-${kind}`}>
                  {confirmation === 'publish'
                    ? `Опубликовать ${materialLabels[kind].toLocaleLowerCase('ru-RU')} revision ${selectedRevision?.data.revisionNumber} сейчас?`
                    : confirmation === 'schedule'
                      ? `Запланировать revision ${selectedRevision?.data.revisionNumber} на ${state.scheduleAt.replace('T', ' ')} (${businessTimezone})?`
                      : confirmation === 'rollback'
                        ? `Вернуть опубликованный материал к revision ${rollbackRevision?.data.revisionNumber}?`
                        : `Скрыть опубликованное ${materialLabels[kind].toLocaleLowerCase('ru-RU')} у школьников и семей?`}
                </p>
                <p className="text-caption text-muted-foreground">
                  {confirmation === 'hide'
                    ? 'История сохранится, но материал перестанет быть доступен для чтения.'
                    : confirmation === 'schedule'
                      ? 'Дедлайн сдачи при этом не изменится.'
                      : 'Действие изменит видимую опубликованную версию.'}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={state.mutationPending}
                    onClick={() => {
                      if (confirmation === 'publish') void publish('publish')
                      else if (confirmation === 'schedule') void publish('schedule')
                      else if (confirmation === 'rollback') void rollback()
                      else void hidePublication()
                    }}
                    size="sm"
                  >
                    {state.mutationPending ? 'Сохраняем…' : 'Подтвердить'}
                  </Button>
                  <Button
                    disabled={state.mutationPending}
                    onClick={() => setConfirmation(null)}
                    size="sm"
                    variant="ghost"
                  >
                    Отмена
                  </Button>
                </div>
              </div>
            ) : null}
            {state.currentPublication ? (
              <p className="flex items-center gap-1 text-caption text-status-success" role="status">
                <CheckCircle2 aria-hidden="true" className="size-3.5" />
                Публичная revision: {state.currentPublication.data.revisionId}
              </p>
            ) : null}
            {state.scheduledPublication ? (
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-caption text-muted-foreground" role="status">
                  Запланировано на{' '}
                  {formatInBusinessTimezone(
                    state.scheduledPublication.data.scheduledAt!,
                    businessTimezone,
                  )}{' '}
                  ({businessTimezone})
                </p>
                <Button
                  disabled={state.mutationPending}
                  onClick={() => void cancelSchedule()}
                  size="xs"
                  variant="ghost"
                >
                  Отменить расписание
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function StaffContentWorkspace({
  client,
  groupLessonId,
}: {
  client: ContentApiClient
  groupLessonId: string
}) {
  const history = useStaffContentHistoryQuery(client, groupLessonId)
  if (history.isPending) {
    return (
      <PageLayout title="LaTeX и публикации" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (history.error) {
    const state =
      history.error instanceof ApiResponseError && history.error.status === 403
        ? 'forbidden'
        : history.error instanceof ApiResponseError && history.error.status === 404
          ? 'empty'
          : 'error'
    return (
      <PageLayout title="LaTeX и публикации" width="wide">
        <PageStatePanel
          {...(state === 'error'
            ? { actionLabel: 'Повторить', onAction: () => void history.refetch() }
            : {})}
          state={state}
          {...(state === 'empty'
            ? {
                title: 'Групповое занятие не найдено',
                description: 'Проверьте ссылку или создайте занятие перед загрузкой LaTeX.',
              }
            : {})}
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description="Условие, подсказка и решение имеют отдельные revision, preview и действия публикации."
      eyebrow={`Групповое занятие ${groupLessonId}`}
      title="LaTeX и публикации"
      width="wide"
    >
      <Alert className="mb-4" tone="info">
        <FileCode2 aria-hidden="true" />
        <AlertContent>
          <AlertTitle>LaTeX — единственный источник</AlertTitle>
          <AlertDescription>
            Сначала проверьте PWA и Telegram preview. Изменение времени решения не меняет дедлайн
            сдачи.
          </AlertDescription>
        </AlertContent>
      </Alert>
      <div className="space-y-4">
        {materialOrder.map((kind) => (
          <MaterialWorkflowCard
            client={client}
            businessTimezone={history.data.businessTimezone}
            groupLessonId={groupLessonId}
            history={materialHistoryFor(history.data.materials, kind)}
            key={kind}
            kind={kind}
            onConflict={() => history.refetch()}
          />
        ))}
      </div>
    </PageLayout>
  )
}

export function StaffLessonContentPage({ lessonId }: { lessonId: string }) {
  const authentication = useAuthentication()
  const client = useMemo(
    () =>
      createContentApiClient(authentication.client.runtime, {
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
  return <StaffContentWorkspace client={client} groupLessonId={lessonId} />
}

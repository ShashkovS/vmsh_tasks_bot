import { AlertTriangle, CheckCircle2, FileCode2, RefreshCw, Send, Upload } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createStaffFamilyDigestClient,
  type StaffFamilyDigestClient,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  SemanticMathDocument,
  TelegramMathHtml,
  createContentApiClient,
  type ContentApiClient,
  type PublicationSlotVersion,
  type StaffLessonWindowClient,
  type VersionedContentResource,
  useStaffContentHistoryQuery,
  useStaffLessonWindowQuery,
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
  type StaffLessonWindow,
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@vmsh/ui'

import { RevisionAssetsRecovery } from './revision-assets-recovery'
import { ProblemReviewWorkflow } from './problem-review-workflow'
import { BulkContentUpload } from './bulk-content-upload'
import { FamilyDigestPanel } from './family-digest-panel'
import { stableBrowserFile } from './stable-browser-file'

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
  processingMessage: string | undefined
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

type LessonWindowDraft = {
  opensLocalTime: string
  submissionClosesLocalTime: string
  hintScheduledLocalTime: string
  solutionScheduledLocalTime: string
}

function localInput(value: string | null, timezone: string): string {
  if (value === null) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: timezone,
  }).formatToParts(new Date(value))
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`
}

function nowLocal(timezone: string): string {
  return localInput(new Date().toISOString(), timezone)
}

function readWindowDraft(key: string): LessonWindowDraft | null {
  try {
    const value: unknown = JSON.parse(globalThis.localStorage.getItem(key) ?? 'null')
    if (value === null || typeof value !== 'object') return null
    return value as LessonWindowDraft
  } catch {
    return null
  }
}

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
    processingMessage: undefined,
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
  if (
    error instanceof ApiResponseError &&
    (error.code === 'asset_conversion_failed' || error.code === 'content_assets_unavailable')
  ) {
    const details = error.details as Record<string, unknown> | undefined
    const logicalAsset = typeof details?.logicalAsset === 'string' ? details.logicalAsset : undefined
    const capability = typeof details?.capability === 'string' ? details.capability : undefined
    const detail = typeof details?.detail === 'string' ? details.detail : undefined
    const subject = logicalAsset ? `Рисунок TikZ ${logicalAsset}` : 'Рисунок TikZ'
    if (error.code === 'content_assets_unavailable') {
      return `${subject}: на сервере временно недоступен ${capability ?? 'нужный конвертер'}. Повторите позднее.`
    }
    return `${subject} не удалось преобразовать в SVG${detail ? `: ${detail}` : '.'}`
  }
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

function revisionLabel(revision: StaffContentRevision, timezone: BusinessTimezone): string {
  return `Версия ${revision.revisionNumber} · ${revision.logicalFilename} · ${formatInBusinessTimezone(revision.uploadedAt, timezone)}`
}

function hintPreviewWithConditions(
  condition: WebContentDocument,
  hint: WebContentDocument,
): WebContentDocument {
  const hints = new Map(hint.problems.map((problem) => [problem.ordinal, problem]))
  return {
    ...hint,
    title: condition.title,
    introduction: condition.introduction,
    problems: condition.problems.map((problem) => {
      const matchingHint = hints.get(problem.ordinal)
      return {
        ...problem,
        blocks: matchingHint
          ? [
              ...problem.blocks,
              {
                type: 'callout' as const,
                kind: 'note' as const,
                title: 'Подсказка',
                blocks: matchingHint.blocks,
              },
            ]
          : problem.blocks,
      }
    }),
  }
}

function MaterialWorkflowCard({
  client,
  draftNamespace,
  groupLessonId,
  history,
  kind,
  conditionRevisionId,
  businessTimezone,
  onConflict,
}: {
  client: ContentApiClient
  draftNamespace: string
  groupLessonId: string
  history: StaffContentMaterialHistory
  kind: ContentMaterialKind
  conditionRevisionId?: string
  businessTimezone: BusinessTimezone
  onConflict: () => Promise<unknown>
}) {
  const [state, setState] = useState<MaterialWorkflowState>(() => initialMaterialState(history))
  const [confirmation, setConfirmation] = useState<ConfirmationAction | null>(null)
  // Button disabled state is applied on the next React render. Keep one
  // synchronous guard too: otherwise a double click can recompile a revision
  // after its first request has already made it terminal.
  const selectedFileCompilePendingRef = useRef(false)
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
  const publishedRevision = state.currentPublication
    ? state.revisions.find(
        (revision) => revision.data.revisionId === state.currentPublication?.data.revisionId,
      )
    : undefined
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
      const previousLatestNumber = current.revisions.at(-1)?.data.revisionNumber ?? 0
      const latestReady = ready.at(-1)
      const selectedRevisionId =
        latestReady && latestReady.data.revisionNumber > previousLatestNumber
          ? latestReady.data.revisionId
          : ready.some((revision) => revision.data.revisionId === current.selectedRevisionId)
            ? current.selectedRevisionId
            : latestReady?.data.revisionId
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
    const [inspected, webPreview, telegramPreview, pdf, conditionWeb, conditionTelegram] =
      await Promise.all([
        client.diagnostics(revisionId),
        client.preview(revisionId, 'web'),
        client.preview(revisionId, 'telegram'),
        optionalPdfPreview(client, revisionId),
        kind === 'hint' && conditionRevisionId
          ? client.preview(conditionRevisionId, 'web')
          : Promise.resolve(undefined),
        kind === 'hint' && conditionRevisionId
          ? client.preview(conditionRevisionId, 'telegram')
          : Promise.resolve(undefined),
      ])
    if (webPreview.kind !== 'web' || telegramPreview.kind !== 'telegram') {
      throw new Error('Сервер вернул несовместимые preview')
    }
    setState((current) => ({
      ...current,
      phase: 'ready',
      processingMessage: undefined,
      revisions: [
        ...current.revisions.filter(
          (revision) => revision.data.revisionId !== inspected.data.revisionId,
        ),
        inspected,
      ].sort((left, right) => left.data.revisionNumber - right.data.revisionNumber),
      selectedRevisionId: inspected.data.revisionId,
      reviewReadyRevisionId: undefined,
      webDocument:
        kind === 'hint' && conditionWeb?.kind === 'web'
          ? hintPreviewWithConditions(conditionWeb.document, webPreview.document)
          : webPreview.document,
      telegramHtml:
        kind === 'hint' && conditionTelegram?.kind === 'telegram'
          ? `${conditionTelegram.html}<hr/><h2>Подсказки</h2>${telegramPreview.html}`
          : telegramPreview.html,
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
      processingMessage: 'Проверяем LaTeX-файл…',
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
      // A short second click (or a second Staff tab) can reach a revision just
      // after its first compile has made it terminal.  A 409 then describes the
      // stale action, not what Staff needs to fix.  Read the durable outcome
      // before presenting a generic conflict; see Phase 2 asset recovery.
      if (error instanceof ApiResponseError && error.status === 409) {
        try {
          const inspected = await client.diagnostics(revision.data.revisionId)
          if (inspected.data.status === 'invalid') {
            setState((current) => ({
              ...current,
              phase: 'invalid',
              processingMessage: undefined,
              invalidRevision: inspected.data,
              previewLoading: false,
              errorMessage: undefined,
            }))
            return
          }
          if (inspected.data.status === 'ready') {
            await inspectCompiledRevision(inspected.data.revisionId)
            return
          }
        } catch {
          // The original conflict remains the best actionable result when the
          // diagnostic read itself cannot complete.
        }
      }
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
          processingMessage: undefined,
          invalidRevision: invalidRevision.data,
          previewLoading: false,
          errorMessage: missingAssets?.success ? undefined : errorMessage(error),
        }))
      } else {
        patchState({ phase: 'error', processingMessage: undefined })
        handleMutationError(error)
      }
    }
  }

  const compileSelectedFile = async () => {
    if (!state.file || selectedFileCompilePendingRef.current) return
    selectedFileCompilePendingRef.current = true
    patchState({ phase: 'processing', errorMessage: undefined, processingMessage: 'Читаем LaTeX-файл…' })
    try {
      const sourceText = await state.file.text()
      if (/\\(?:begin\s*\{tikzpicture\}|tikz\b)/u.test(sourceText)) {
        patchState({ processingMessage: 'Готовим рисунки из TikZ. Это может занять немного времени…' })
      } else {
        patchState({ processingMessage: 'Загружаем и проверяем LaTeX-файл…' })
      }
      const uploaded = await client.uploadSource({
        groupLessonId,
        kind,
        logicalFilename: state.file.name,
        source: state.file,
      })
      setState((current) => ({
        ...current,
        processingMessage: 'Проверяем структуру материала…',
        revisions: [
          ...current.revisions.filter(
            (revision) => revision.data.revisionId !== uploaded.data.revisionId,
          ),
          uploaded,
        ].sort((left, right) => left.data.revisionNumber - right.data.revisionNumber),
      }))
      if (uploaded.data.status === 'ready') await inspectCompiledRevision(uploaded.data.revisionId)
      else await compileStoredRevision(uploaded)
    } catch (error) {
      patchState({ phase: 'error', processingMessage: undefined })
      handleMutationError(error)
    } finally {
      selectedFileCompilePendingRef.current = false
    }
  }

  const loadSelectedPreviews = async () => {
    if (!selectedRevision) return
    patchState({ previewLoading: true, errorMessage: undefined })
    try {
      const [webPreview, telegramPreview, pdf, conditionWeb, conditionTelegram] = await Promise.all(
        [
          client.preview(selectedRevision.data.revisionId, 'web'),
          client.preview(selectedRevision.data.revisionId, 'telegram'),
          optionalPdfPreview(client, selectedRevision.data.revisionId),
          kind === 'hint' && conditionRevisionId
            ? client.preview(conditionRevisionId, 'web')
            : Promise.resolve(undefined),
          kind === 'hint' && conditionRevisionId
            ? client.preview(conditionRevisionId, 'telegram')
            : Promise.resolve(undefined),
        ],
      )
      if (webPreview.kind !== 'web' || telegramPreview.kind !== 'telegram') {
        throw new Error('Сервер вернул несовместимые preview')
      }
      patchState({
        previewLoading: false,
        webDocument:
          kind === 'hint' && conditionWeb?.kind === 'web'
            ? hintPreviewWithConditions(conditionWeb.document, webPreview.document)
            : webPreview.document,
        telegramHtml:
          kind === 'hint' && conditionTelegram?.kind === 'telegram'
            ? `${conditionTelegram.html}<hr/><h2>Подсказки</h2>${telegramPreview.html}`
            : telegramPreview.html,
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
    if (!selectedRevision) return
    // The confirmation was reachable only after the review became ready. A
    // concurrent Staff invalidation may briefly reset that child projection
    // before the user confirms; silently dropping the click would lose an
    // explicit action. The Phase 2 API rechecks revision status, matching and
    // metadata authoritatively in publish_content_revision.
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
    <Card data-testid={`content-workflow-${kind}`} id={`material-${kind}`}>
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
                const selected = event.currentTarget.files?.[0]
                if (!selected) return
                void stableBrowserFile(selected).then(
                  (file) => {
                    setState((current) => ({
                      ...current,
                      file,
                      phase: 'idle',
                      processingMessage: undefined,
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
                  },
                  () => {
                    patchState({
                      file: undefined,
                      phase: 'error',
                      errorMessage:
                        'Не удалось прочитать выбранный файл. Скопируйте его на локальный диск и выберите ещё раз.',
                    })
                  },
                )
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
            {state.phase === 'processing' ? 'Обрабатываем…' : 'Загрузить и проверить'}
          </Button>
        </div>

        {state.phase === 'processing' && state.processingMessage ? (
          <p className="inline-flex items-center gap-2 text-small text-muted-foreground" role="status">
            <RefreshCw aria-hidden="true" className="size-4 animate-spin" />
            {state.processingMessage}
          </p>
        ) : null}

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
                    Версия {revision.data.revisionNumber} · {revision.data.logicalFilename}
                    <span className="ml-1 text-muted-foreground">
                      {revision.data.status === 'uploaded'
                        ? 'загружена, но не проверена'
                        : 'проверка прервалась'}
                    </span>
                  </span>
                  <Button
                    aria-label={`Найти недостающие рисунки в версии ${revision.data.revisionNumber}`}
                    disabled={state.phase === 'processing'}
                    onClick={() => void compileStoredRevision(revision)}
                    size="xs"
                    variant="outline"
                  >
                    <RefreshCw aria-hidden="true" /> Найти недостающие рисунки
                  </Button>
                </li>
              ))}
              {activeCompilations.map((revision) => (
                <li className="text-small text-muted-foreground" key={revision.data.revisionId}>
                  Версия {revision.data.revisionNumber} проверяется. Повтор станет доступен после
                  завершения текущей сборки.
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {readyRevisions.length > 1 ? (
          <div className="max-w-md space-y-1">
            <Label htmlFor={`ready-revision-${kind}`}>Версия для проверки и публикации</Label>
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
                    ? revisionLabel(selectedRevision.data, businessTimezone)
                    : 'Выберите версию'}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {[...readyRevisions].reverse().map((revision) => (
                  <SelectItem key={revision.data.revisionId} value={revision.data.revisionId}>
                    {revisionLabel(revision.data, businessTimezone)}
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
              <AlertTitle>Диагностика версии {visibleRevision?.revisionNumber}</AlertTitle>
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
            draftNamespace={draftNamespace}
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
            {state.previewLoading ? 'Загружаем предпросмотр…' : 'Показать PWA и Telegram'}
          </Button>
        ) : null}

        {state.webDocument &&
        state.telegramHtml &&
        state.previewRevisionId === selectedRevision?.data.revisionId ? (
          <section aria-label={`Preview: ${materialLabels[kind]}`} className="min-w-0">
            <Tabs defaultValue="pwa">
              <TabsList aria-label="Вариант предпросмотра" variant="line">
                <TabsTrigger value="pwa">PWA</TabsTrigger>
                <TabsTrigger value="telegram">Telegram</TabsTrigger>
                <TabsTrigger value="pdf">PDF</TabsTrigger>
              </TabsList>
              <TabsContent className="min-w-0" value="pwa">
                <div className="mx-auto max-w-[52rem] rounded-md border border-border bg-surface p-4 sm:p-6">
                  <SemanticMathDocument document={state.webDocument} />
                </div>
              </TabsContent>
              <TabsContent className="min-w-0" value="telegram">
                <div className="mx-auto max-w-[42rem] rounded-md border border-border bg-surface p-4 sm:p-5">
                  <TelegramMathHtml html={state.telegramHtml} />
                </div>
              </TabsContent>
              <TabsContent className="min-w-0" value="pdf">
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
                    <p className="text-muted-foreground">PDF для этой версии пока не сохранён.</p>
                  )}
                </div>
              </TabsContent>
            </Tabs>
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
                  <Label htmlFor={`rollback-revision-${kind}`}>Версия для отката</Label>
                  <Select
                    onValueChange={(value) => value && patchState({ rollbackRevisionId: value })}
                    value={state.rollbackRevisionId}
                  >
                    <SelectTrigger className="w-full" id={`rollback-revision-${kind}`}>
                      <SelectValue>
                        {rollbackRevision
                          ? `Версия ${rollbackRevision.data.revisionNumber} · ${rollbackRevision.data.logicalFilename}`
                          : 'Выберите версию'}
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
                            Версия {revision.data.revisionNumber} · {revision.data.logicalFilename}
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
                    ? `Опубликовать ${materialLabels[kind].toLocaleLowerCase('ru-RU')} версии ${selectedRevision?.data.revisionNumber} сейчас?`
                    : confirmation === 'schedule'
                      ? `Запланировать версию ${selectedRevision?.data.revisionNumber} на ${state.scheduleAt.replace('T', ' ')} (${businessTimezone})?`
                      : confirmation === 'rollback'
                        ? `Вернуть опубликованный материал к версии ${rollbackRevision?.data.revisionNumber}?`
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
                Опубликована{' '}
                {publishedRevision
                  ? `версия ${publishedRevision.data.revisionNumber} · ${publishedRevision.data.logicalFilename}`
                  : 'текущая версия'}
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

function LessonWindowPanel(props: {
  client: ContentApiClient
  draftNamespace: string
  groupLessonId: string
}) {
  const { client } = props
  if (
    !client.lessonWindow ||
    !client.updateLessonWindowSchedule ||
    !client.updateSubmissionCutoff
  ) {
    return null
  }
  return <LessonWindowPanelEnabled {...props} client={client as StaffLessonWindowClient} />
}

function LessonWindowPanelEnabled({
  client,
  draftNamespace,
  groupLessonId,
}: {
  client: StaffLessonWindowClient
  draftNamespace: string
  groupLessonId: string
}) {
  const query = useStaffLessonWindowQuery(client, groupLessonId)
  if (query.isPending) return <PageStatePanel state="loading" />
  if (query.error) return <PageStatePanel state="error" />
  return (
    <LessonWindowEditor
      client={client}
      draftKey={`${draftNamespace}:lesson-window:${groupLessonId}`}
      groupLessonId={groupLessonId}
      onRefetch={() => query.refetch()}
      resource={query.data}
    />
  )
}

function LessonWindowEditor({
  client,
  draftKey,
  groupLessonId,
  onRefetch,
  resource,
}: {
  client: StaffLessonWindowClient
  draftKey: string
  groupLessonId: string
  onRefetch: () => Promise<unknown>
  resource: VersionedContentResource<StaffLessonWindow>
}) {
  const window = resource.data
  const [draft, setDraft] = useState<LessonWindowDraft>(
    () =>
      readWindowDraft(draftKey) ?? {
        opensLocalTime: localInput(window.opensAt, window.businessTimezone),
        submissionClosesLocalTime: localInput(window.submissionClosesAt, window.businessTimezone),
        hintScheduledLocalTime: localInput(window.hintScheduledAt, window.businessTimezone),
        solutionScheduledLocalTime: localInput(window.solutionScheduledAt, window.businessTimezone),
      },
  )
  const [pending, setPending] = useState<'schedule' | 'cutoff' | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    globalThis.localStorage.setItem(draftKey, JSON.stringify(draft))
  }, [draft, draftKey])

  async function saveSchedule() {
    setPending('schedule')
    setError(null)
    try {
      await client.updateLessonWindowSchedule(groupLessonId, resource.etag, {
        opensLocalTime: draft.opensLocalTime || null,
        hintScheduledLocalTime: draft.hintScheduledLocalTime || null,
        solutionScheduledLocalTime: draft.solutionScheduledLocalTime || null,
        businessTimezone: window.businessTimezone,
      })
      await onRefetch()
    } catch (caught) {
      setError(caught instanceof ApiResponseError ? caught.message : 'Изменение не сохранено')
    } finally {
      setPending(null)
    }
  }

  async function saveCutoff(value = draft.submissionClosesLocalTime) {
    if (!value) return
    setPending('cutoff')
    setError(null)
    try {
      await client.updateSubmissionCutoff(groupLessonId, resource.etag, {
        submissionClosesLocalTime: value,
        businessTimezone: window.businessTimezone,
        confirmChange: true,
      })
      setDraft((current) => ({ ...current, submissionClosesLocalTime: value }))
      await onRefetch()
    } catch (caught) {
      setError(caught instanceof ApiResponseError ? caught.message : 'Дедлайн не изменён')
    } finally {
      setPending(null)
    }
  }

  function confirmCutoffChange(value = draft.submissionClosesLocalTime) {
    if (!value) return
    if (!globalThis.confirm(`Изменить дедлайн сдачи на ${value.replace('T', ' ')}?`)) return
    void saveCutoff(value)
  }

  const timezone = window.businessTimezone
  return (
    <Card>
      <CardHeader>
        <CardTitle>Фазы занятия</CardTitle>
        <p className="text-small text-muted-foreground">
          Время указано для {timezone}. Дедлайн меняется отдельно от публикации решений.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 md:grid-cols-3">
          <Label className="grid gap-1">
            Открыть приём
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, opensLocalTime: event.target.value }))
              }
              type="datetime-local"
              value={draft.opensLocalTime}
            />
          </Label>
          <Label className="grid gap-1">
            Подсказки
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, hintScheduledLocalTime: event.target.value }))
              }
              type="datetime-local"
              value={draft.hintScheduledLocalTime}
            />
          </Label>
          <Label className="grid gap-1">
            Решения
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, solutionScheduledLocalTime: event.target.value }))
              }
              type="datetime-local"
              value={draft.solutionScheduledLocalTime}
            />
          </Label>
        </div>
        <Button disabled={pending !== null} onClick={() => void saveSchedule()} size="sm">
          Сохранить расписание публикаций
        </Button>
        <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
          <Label className="grid gap-1">
            Дедлайн сдачи
            <Input
              onChange={(event) =>
                setDraft((value) => ({
                  ...value,
                  submissionClosesLocalTime: event.target.value,
                }))
              }
              required
              type="datetime-local"
              value={draft.submissionClosesLocalTime}
            />
          </Label>
          <Button disabled={pending !== null} onClick={() => confirmCutoffChange()} size="sm">
            Изменить дедлайн
          </Button>
          <Button
            disabled={pending !== null}
            onClick={() => confirmCutoffChange(nowLocal(timezone))}
            size="sm"
            variant="outline"
          >
            Закрыть приём сейчас
          </Button>
        </div>
        {error ? (
          <p className="text-small text-status-error" role="alert">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function StaffContentWorkspace({
  client,
  draftNamespace,
  familyDigest,
  groupLessonId,
}: {
  client: ContentApiClient
  draftNamespace: string
  familyDigest?: {
    client: StaffFamilyDigestClient
    scope: { audience: 'staff'; accountId: string }
  }
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

  const conditionRevisionId = materialHistoryFor(history.data.materials, 'condition')
    .revisions.filter(
      (revision) => revision.status === 'ready' && revision.missingAssets.length === 0,
    )
    .at(-1)?.revisionId

  return (
    <PageLayout
      description="Условие, подсказка и решение имеют отдельные версии, предпросмотр и действия публикации."
      eyebrow={`Групповое занятие ${groupLessonId}`}
      title="LaTeX и публикации"
      width="wide"
    >
      <Alert className="mb-4" tone="info">
        <FileCode2 aria-hidden="true" />
        <AlertContent>
          <AlertTitle>LaTeX — единственный источник</AlertTitle>
          <AlertDescription>
            Сначала проверьте версии для PWA и Telegram. Изменение времени решения не меняет дедлайн
            сдачи.
          </AlertDescription>
        </AlertContent>
      </Alert>
      <div className="space-y-4">
        <LessonWindowPanel
          client={client}
          draftNamespace={draftNamespace}
          groupLessonId={groupLessonId}
        />
        <BulkContentUpload
          client={client}
          groupLessonId={groupLessonId}
          onCompleted={() => history.refetch()}
        />
        {materialOrder.map((kind) => (
          <MaterialWorkflowCard
            client={client}
            draftNamespace={draftNamespace}
            businessTimezone={history.data.businessTimezone}
            {...(conditionRevisionId ? { conditionRevisionId } : {})}
            groupLessonId={groupLessonId}
            history={materialHistoryFor(history.data.materials, kind)}
            key={kind}
            kind={kind}
            onConflict={() => history.refetch()}
          />
        ))}
        {familyDigest ? (
          <FamilyDigestPanel
            client={familyDigest.client}
            groupLessonId={groupLessonId}
            scope={familyDigest.scope}
          />
        ) : null}
      </div>
    </PageLayout>
  )
}

export function StaffLessonContentPage({ lessonId }: { lessonId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
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
  const familyDigestClient = useMemo(
    () =>
      createStaffFamilyDigestClient(authentication.client.runtime, {
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
  const canSendFamilyDigest =
    principal.audience === 'staff' &&
    principal.role === 'admin' &&
    principal.capabilities.includes('broadcast.manage')
  return (
    <StaffContentWorkspace
      client={client}
      draftNamespace={`${authentication.client.runtime.instance}:${principal.accountId}`}
      {...(canSendFamilyDigest
        ? {
            familyDigest: {
              client: familyDigestClient,
              scope: { audience: 'staff' as const, accountId: principal.accountId },
            },
          }
        : {})}
      groupLessonId={lessonId}
    />
  )
}

import { answerTypeOptions, metadataColumns, problemTypeOptions } from './problem-metadata-columns'
import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { CheckCircle2, LoaderCircle, Pencil, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { type ContentApiClient, type VersionedContentResource } from '@vmsh/content'
import { recordProductAction } from '@vmsh/app-shell'
import {
  ApiResponseError,
  answerTypeSchema,
  problemTypeSchema,
  problemMetadataGenerationTypesSchema,
  type ContentMaterialKind,
  type ProblemMatchReview,
  type ProblemMetadataGrid,
  type ProblemMetadataMutationRow,
} from '@vmsh/contracts'
import {
  MetadataGrid,
  ProblemMatching,
  type MetadataError,
  type MetadataRow,
  type ProblemMatchingSelection,
} from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Button, Progress } from '@vmsh/ui'

import { automaticProblemMatchPlan } from './automatic-problem-match-plan'
import { problemReviewDraftStorageKey } from './problem-review-draft'

/**
 * Staff adapter for Phase 2 MATCH-01..03 and METADATA-01..02. The product
 * components remain transport-free; this file owns optimistic ETags and
 * revision-scoped local recovery (`06-phase-2-content.md`).
 */

type MatchResource = VersionedContentResource<ProblemMatchReview>
type MetadataResource = VersionedContentResource<ProblemMetadataGrid>
type WorkflowPhase = 'loading' | 'matching' | 'metadata' | 'ready' | 'error'

interface StoredMatchDraft {
  schemaVersion: 1
  etag: string
  selections: Record<string, ProblemMatchingSelection>
}

interface StoredMetadataDraft {
  schemaVersion: 1
  etag: string
  rows: MetadataRow[]
}

const metadataGenerationExpectedSeconds = 70

const typeLabels: Record<number, string> = {
  get 1() {
    return t`тестовая`
  },
  get 2() {
    return t`письменная`
  },
  get 3() {
    return t`устная`
  },
}

function problemKey(sourceOrdinal: number, sourceItem: string): string {
  return JSON.stringify([sourceOrdinal, sourceItem])
}

function readStoredObject(key: string): unknown {
  try {
    const value = globalThis.localStorage?.getItem(key)
    return value ? JSON.parse(value) : undefined
  } catch {
    return undefined
  }
}

function writeStoredObject(key: string, value: unknown): void {
  try {
    globalThis.localStorage?.setItem(key, JSON.stringify(value))
  } catch {
    // Draft recovery is best-effort only; server state remains authoritative.
  }
}

function clearStoredObject(key: string): void {
  try {
    globalThis.localStorage?.removeItem(key)
  } catch {
    // A blocked storage area must not prevent an explicit server save.
  }
}

function selectionsFromReview(
  review: ProblemMatchReview,
): Record<string, ProblemMatchingSelection> {
  const selections: Record<string, ProblemMatchingSelection> = {}
  review.items.forEach((item) => {
    if (!item.match) return
    const key = problemKey(item.sourceOrdinal, item.sourceItem)
    if (item.match.decision === 'omit' || item.match.decision === 'insert_new') {
      selections[key] = { decision: item.match.decision, candidateId: null }
    } else if (item.match.problemId !== null) {
      selections[key] = {
        decision: item.match.decision,
        candidateId: String(item.match.problemId),
      }
    }
  })
  return selections
}

function parseStoredSelections(
  key: string,
  review: ProblemMatchReview,
): { etag: string; selections: Record<string, ProblemMatchingSelection> } | undefined {
  const raw = readStoredObject(key)
  if (!raw || typeof raw !== 'object') return undefined
  const value = raw as Partial<StoredMatchDraft>
  if (value.schemaVersion !== 1 || typeof value.etag !== 'string' || !value.selections) {
    return undefined
  }
  const validKeys = new Set(
    review.items.map((item) => problemKey(item.sourceOrdinal, item.sourceItem)),
  )
  const selections: Record<string, ProblemMatchingSelection> = {}
  for (const [itemKey, selection] of Object.entries(value.selections)) {
    if (!validKeys.has(itemKey) || !selection || typeof selection !== 'object') continue
    if (
      (selection.decision === 'insert_new' || selection.decision === 'omit') &&
      selection.candidateId === null
    ) {
      selections[itemKey] = selection
    } else if (
      (selection.decision === 'auto_position' || selection.decision === 'manual_match') &&
      typeof selection.candidateId === 'string' &&
      selection.candidateId !== ''
    ) {
      selections[itemKey] = selection
    }
  }
  return { etag: value.etag, selections }
}

function metadataRow(row: ProblemMetadataGrid['rows'][number]): MetadataRow {
  return {
    problemId: String(row.problemId),
    sourceOrdinal: String(row.sourceOrdinal),
    sourceItem: row.sourceItem,
    displayNumber: row.displayNumber,
    title: row.title,
    problemType: String(row.problemType),
    answerType: row.answerType === null ? '' : String(row.answerType),
    answerValidation: row.answerValidation ?? '',
    validationError: row.validationError ?? '',
    correctAnswer: row.correctAnswer ?? '',
    correctAnswerChecker: row.correctAnswerChecker ?? '',
    wrongAnswer: row.wrongAnswer ?? '',
    congratulation: row.congratulation ?? '',
  }
}

function generatedMetadataRow(row: ProblemMetadataMutationRow): MetadataRow {
  return {
    problemId: String(row.problemId),
    sourceOrdinal: String(row.sourceOrdinal),
    sourceItem: row.sourceItem,
    displayNumber: row.displayNumber,
    title: row.title,
    problemType: String(row.problemType),
    answerType: row.answerType === null ? '' : String(row.answerType),
    answerValidation: row.answerValidation ?? '',
    validationError: row.validationError ?? '',
    correctAnswer: row.correctAnswer ?? '',
    correctAnswerChecker: row.correctAnswerChecker ?? '',
    wrongAnswer: row.wrongAnswer ?? '',
    congratulation: row.congratulation ?? '',
  }
}

function sameMetadataIdentity(left: MetadataRow, right: MetadataRow): boolean {
  return (
    left.problemId === right.problemId &&
    left.sourceOrdinal === right.sourceOrdinal &&
    left.sourceItem === right.sourceItem
  )
}

function storedMetadataRows(
  key: string,
  grid: ProblemMetadataGrid,
): StoredMetadataDraft | undefined {
  const raw = readStoredObject(key)
  if (!raw || typeof raw !== 'object') return undefined
  const value = raw as Partial<StoredMetadataDraft>
  if (value.schemaVersion !== 1 || typeof value.etag !== 'string' || !Array.isArray(value.rows)) {
    return undefined
  }
  const baseline = grid.rows.map(metadataRow)
  const rows = value.rows.filter(
    (row): row is MetadataRow =>
      !!row &&
      typeof row === 'object' &&
      Object.values(row).every((cell) => typeof cell === 'string'),
  )
  if (
    rows.length !== baseline.length ||
    rows.some((row, index) => !sameMetadataIdentity(row, baseline[index]!))
  ) {
    return undefined
  }
  return { schemaVersion: 1, etag: value.etag, rows }
}

function validateMetadataRows(rows: MetadataRow[]): MetadataError[] {
  const errors: MetadataError[] = []
  rows.forEach((row, index) => {
    if (!row.title?.trim()) {
      errors.push({ row: index, col: 'title', message: t`Заполните короткое название задачи` })
    }
    if (!problemTypeOptions.some((option) => option.value === row.problemType)) {
      errors.push({ row: index, col: 'problemType', message: t`Выберите тип задачи` })
    }
    if (
      row.problemType === '1' &&
      !answerTypeOptions.some((item) => item.value === row.answerType)
    ) {
      errors.push({
        row: index,
        col: 'answerType',
        message: t`Для тестовой задачи нужен тип ответа`,
      })
    }
    if (row.problemType !== '1') {
      const answerFields = [
        'answerType',
        'answerValidation',
        'validationError',
        'correctAnswer',
        'correctAnswerChecker',
        'wrongAnswer',
        'congratulation',
      ]
      answerFields.forEach((field) => {
        if (row[field]?.trim()) {
          errors.push({
            row: index,
            col: field,
            message: t`Поля ответа доступны только для тестовой задачи`,
          })
        }
      })
    }
  })
  return errors
}

function metadataMutationRows(rows: MetadataRow[]): ProblemMetadataMutationRow[] {
  return rows.map((row) => ({
    problemId: Number(row.problemId),
    sourceOrdinal: Number(row.sourceOrdinal),
    sourceItem: row.sourceItem ?? '',
    displayNumber: row.displayNumber ?? '',
    title: row.title ?? '',
    problemType: problemTypeSchema.parse(Number(row.problemType)),
    answerType: row.answerType ? answerTypeSchema.parse(Number(row.answerType)) : null,
    answerValidation: row.answerValidation || null,
    validationError: row.validationError || null,
    correctAnswer: row.correctAnswer || null,
    correctAnswerChecker: row.correctAnswerChecker || null,
    wrongAnswer: row.wrongAnswer || null,
    congratulation: row.congratulation || null,
  }))
}

function readableError(error: unknown): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof Error) return error.message
  return t`Не удалось загрузить проверку задач`
}

export function ProblemReviewWorkflow({
  client,
  draftNamespace,
  groupLessonId,
  revisionId,
  kind,
  onReadyChange,
}: {
  client: ContentApiClient
  draftNamespace: string
  groupLessonId: string
  revisionId: string
  kind: ContentMaterialKind
  onReadyChange: (revisionId: string, ready: boolean) => void
}) {
  const [phase, setPhase] = useState<WorkflowPhase>('loading')
  const [matchResource, setMatchResource] = useState<MatchResource>()
  const [metadataResource, setMetadataResource] = useState<MetadataResource>()
  const [selections, setSelections] = useState<Record<string, ProblemMatchingSelection>>({})
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string>()
  const [staleDraft, setStaleDraft] = useState(false)
  const [generatedRows, setGeneratedRows] = useState<MetadataRow[]>()
  const metadataRowsRef = useRef<MetadataRow[]>([])
  const [metadataDirty, setMetadataDirty] = useState(false)
  const [generationWarnings, setGenerationWarnings] = useState<string[]>([])
  const [metadataGridEpoch, setMetadataGridEpoch] = useState(0)
  const [metadataGenerationStartedAt, setMetadataGenerationStartedAt] = useState<number>()
  const [metadataGenerationElapsedSeconds, setMetadataGenerationElapsedSeconds] = useState(0)

  useEffect(() => {
    if (metadataGenerationStartedAt === undefined) return
    const updateElapsed = () => {
      setMetadataGenerationElapsedSeconds(
        Math.floor((Date.now() - metadataGenerationStartedAt) / 1_000),
      )
    }
    updateElapsed()
    const interval = window.setInterval(updateElapsed, 1_000)
    return () => window.clearInterval(interval)
  }, [metadataGenerationStartedAt])

  const matchDraftKey = problemReviewDraftStorageKey(
    draftNamespace,
    'matching',
    groupLessonId,
    revisionId,
  )
  const metadataDraftKey = problemReviewDraftStorageKey(
    draftNamespace,
    'metadata',
    groupLessonId,
    revisionId,
  )

  const acceptMetadata = useCallback(
    (resource: MetadataResource) => {
      setMetadataResource(resource)
      const draft = storedMetadataRows(metadataDraftKey, resource.data)
      metadataRowsRef.current = draft?.rows ?? resource.data.rows.map(metadataRow)
      setGeneratedRows(undefined)
      setMetadataDirty(false)
      setGenerationWarnings([])
      if (!draft && resource.data.rows.every((row) => row.reviewed)) {
        clearStoredObject(metadataDraftKey)
        setPhase('ready')
        return
      }
      setStaleDraft(draft !== undefined && draft.etag !== resource.etag)
      setPhase('metadata')
    },
    [metadataDraftKey],
  )

  const advanceAfterMatching = useCallback(
    async (resource: MatchResource) => {
      let current = resource
      setMatchResource(current)
      let allMatched = current.data.items.every((item) => item.match !== null)
      if (!allMatched) {
        const automaticPlan = automaticProblemMatchPlan(current.data, kind === 'condition')
        if (automaticPlan) {
          try {
            current = await client.resolveProblemMatches({
              revisionId,
              etag: current.etag,
              matches: automaticPlan,
            })
          } catch (error) {
            if (!(error instanceof ApiResponseError) || error.status !== 409) throw error
            // React development effects and two open Staff tabs may race on
            // the same harmless automatic transition. Read the winner instead
            // of turning that race into a dead-end form.
            current = await client.problemMatches(revisionId)
          }
          setMatchResource(current)
          allMatched = current.data.items.every((item) => item.match !== null)
        } else if (kind !== 'condition') {
          throw new Error(
            t`Структура задач или пунктов не совпадает с условием. Исправьте LaTeX-файл и загрузите новую revision.`,
          )
        }
        if (!allMatched) {
          const stored = parseStoredSelections(matchDraftKey, current.data)
          setSelections(stored?.selections ?? selectionsFromReview(current.data))
          setStaleDraft(stored !== undefined && stored.etag !== current.etag)
          setPhase('matching')
          return
        }
      }
      clearStoredObject(matchDraftKey)
      setStaleDraft(false)
      if (kind !== 'condition') {
        setPhase('ready')
        return
      }
      acceptMetadata(await client.metadataGrid(groupLessonId, revisionId))
    },
    [acceptMetadata, client, groupLessonId, kind, matchDraftKey, revisionId],
  )

  const reload = useCallback(async () => {
    setPhase('loading')
    setMessage(undefined)
    try {
      await advanceAfterMatching(await client.problemMatches(revisionId))
    } catch (error) {
      setMessage(readableError(error))
      setPhase('error')
    }
  }, [advanceAfterMatching, client, revisionId])

  // Parent queries may refresh their client object while Staff is editing a
  // grid. Reloading from that render cycle remounts the keyed grid and loses
  // the open editor/fullscreen state. A revision is loaded only once here;
  // every explicit reload remains user initiated.
  const reloadRef = useRef(reload)
  useEffect(() => {
    reloadRef.current = reload
  }, [reload])

  useEffect(() => {
    const task = globalThis.setTimeout(() => void reloadRef.current(), 0)
    return () => globalThis.clearTimeout(task)
  }, [revisionId])

  useEffect(() => {
    onReadyChange(revisionId, phase === 'ready')
  }, [onReadyChange, phase, revisionId])

  const matchingItems = useMemo(
    () =>
      matchResource?.data.items.map((item) => ({
        key: problemKey(item.sourceOrdinal, item.sourceItem),
        displayNumber: item.displayNumber,
        sourceTitle: item.sourceTitle,
        suggestedCandidateId:
          item.suggestedProblemId === null ? null : String(item.suggestedProblemId),
      })) ?? [],
    [matchResource],
  )

  const matchingCandidates = useMemo(
    () =>
      matchResource?.data.candidates.map((candidate) => ({
        id: String(candidate.problemId),
        number: candidate.problemNumber,
        item: candidate.item,
        title: candidate.title,
        typeLabel: typeLabels[candidate.problemType] ?? t`тип ${candidate.problemType}`,
      })) ?? [],
    [matchResource],
  )

  const saveMatches = async () => {
    if (!matchResource) return
    setPending(true)
    setMessage(undefined)
    try {
      const matches = matchResource.data.items.map((item) => {
        const selection = selections[problemKey(item.sourceOrdinal, item.sourceItem)]
        if (!selection) throw new Error(t`Выберите действие для каждой задачи`)
        return {
          sourceOrdinal: item.sourceOrdinal,
          sourceItem: item.sourceItem,
          decision: selection.decision,
          problemId: selection.candidateId === null ? null : Number(selection.candidateId),
        }
      })
      const saved = await client.resolveProblemMatches({
        revisionId,
        etag: matchResource.etag,
        matches,
      })
      clearStoredObject(matchDraftKey)
      await advanceAfterMatching(saved)
    } catch (error) {
      if (error instanceof ApiResponseError && error.status === 409) {
        const current = await client.problemMatches(revisionId)
        clearStoredObject(matchDraftKey)
        setSelections({})
        setStaleDraft(false)
        await advanceAfterMatching(current)
        if (current.data.items.some((item) => item.match === null)) {
          setMessage(
            t`Сервер уже принял другое изменение. Текущее состояние загружено заново; проверьте только строки, которые нельзя сопоставить автоматически.`,
          )
        }
      } else {
        setMessage(readableError(error))
      }
    } finally {
      setPending(false)
    }
  }

  const editMatches = async () => {
    setPhase('loading')
    setMessage(undefined)
    try {
      const current = await client.problemMatches(revisionId)
      setMatchResource(current)
      setSelections(selectionsFromReview(current.data))
      setStaleDraft(false)
      setPhase('matching')
    } catch (error) {
      setMessage(readableError(error))
      setPhase('error')
    }
  }

  const editMetadata = async () => {
    setPhase('loading')
    setMessage(undefined)
    try {
      const current = await client.metadataGrid(groupLessonId, revisionId)
      setMetadataResource(current)
      metadataRowsRef.current =
        storedMetadataRows(metadataDraftKey, current.data)?.rows ??
        current.data.rows.map(metadataRow)
      setStaleDraft(false)
      setPhase('metadata')
    } catch (error) {
      setMessage(readableError(error))
      setPhase('error')
    }
  }

  const generateMetadata = async (useTableTypes = false) => {
    if (!metadataResource || !client.generateMetadata) return
    // metadata-generation.md: read the live grid, including unsaved subpart
    // edits and sessions where localStorage is unavailable.
    const selectedTypes = useTableTypes
      ? problemMetadataGenerationTypesSchema.safeParse(
          metadataRowsRef.current.map((row) => ({
            problemId: Number(row.problemId),
            problemType: Number(row.problemType),
          })),
        )
      : undefined
    if (selectedTypes && !selectedTypes.success) {
      setMessage(t`Укажите тестовый, письменный или устный тип для каждой задачи.`)
      return
    }
    const confirmedOverwrite =
      metadataResource.data.metadataGenerationRequiresConfirmation === true || metadataDirty
    if (
      confirmedOverwrite &&
      !globalThis.confirm(
        useTableTypes
          ? t`Перегенерировать metadata с типами из таблицы? Типы задач сохранятся, остальные поля черновика будут заменены. Результат нужно проверить и сохранить вручную.`
          : t`Полностью перегенерировать metadata? Текущий черновик и показанная таблица будут заменены результатом модели. После проверки «Сохранить метаданные» заменит сохранённую конфигурацию задач.`,
      )
    ) {
      return
    }
    setPending(true)
    setMessage(undefined)
    setMetadataGenerationElapsedSeconds(0)
    setMetadataGenerationStartedAt(Date.now())
    try {
      const generated = await client.generateMetadata({
        groupLessonId,
        revisionId,
        ...(confirmedOverwrite ? { confirmedOverwrite: true } : {}),
        ...(selectedTypes?.success ? { problemTypes: selectedTypes.data } : {}),
      })
      const rows = generated.rows.map(generatedMetadataRow)
      metadataRowsRef.current = rows
      writeStoredObject(metadataDraftKey, {
        schemaVersion: 1,
        etag: metadataResource.etag,
        rows,
      } satisfies StoredMetadataDraft)
      setGeneratedRows(rows)
      recordProductAction('metadata.generate', { type: 'lesson', id: groupLessonId })
      setGenerationWarnings(generated.warnings)
      setMetadataGridEpoch((epoch) => epoch + 1)
    } catch (error) {
      setMessage(readableError(error))
    } finally {
      setPending(false)
      setMetadataGenerationStartedAt(undefined)
    }
  }

  if (phase === 'loading') {
    return (
      <p className="text-small text-muted-foreground">
        <Trans>Загружаем структуру задач…</Trans>
      </p>
    )
  }

  if (phase === 'error') {
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>
            <Trans>Не удалось загрузить проверку задач</Trans>
          </AlertTitle>
          <AlertDescription>{message}</AlertDescription>
          <Button className="mt-2" onClick={() => void reload()} size="xs" variant="outline">
            <RefreshCw aria-hidden="true" /> <Trans>Повторить</Trans>
          </Button>
        </AlertContent>
      </Alert>
    )
  }

  if (phase === 'matching' && matchResource) {
    return (
      <ProblemMatching
        candidates={matchingCandidates}
        {...(message ? { error: message } : {})}
        id={`problem-matching-${kind}`}
        items={matchingItems}
        onCommit={() => void saveMatches()}
        onSelectionChange={(itemKey, selection) => {
          const next = { ...selections }
          if (selection) next[itemKey] = selection
          else delete next[itemKey]
          setSelections(next)
          setMessage(undefined)
          writeStoredObject(matchDraftKey, {
            schemaVersion: 1,
            etag: matchResource.etag,
            selections: next,
          } satisfies StoredMatchDraft)
        }}
        pending={pending}
        selections={selections}
        staleDraft={staleDraft}
      />
    )
  }

  if (phase === 'metadata' && metadataResource) {
    const baseline = metadataResource.data.rows.map(metadataRow)
    const draft = generatedRows
      ? { schemaVersion: 1 as const, etag: metadataResource.etag, rows: generatedRows }
      : storedMetadataRows(metadataDraftKey, metadataResource.data)
    return (
      <section aria-labelledby={`problem-metadata-${kind}`} className="space-y-2">
        <div>
          <h3 className="text-small font-semibold" id={`problem-metadata-${kind}`}>
            <Trans>Метаданные задач</Trans>
          </h3>
          <p className="text-caption text-muted-foreground">
            <Trans>
              Проверьте названия, способы сдачи и сообщения проверки. Таблица сохраняется локально
              до подтверждения. Сохранение заменяет текущую конфигурацию задачи; для тестовой задачи
              затем перепроверьте ответы по новой конфигурации.
            </Trans>
          </p>
        </div>
        {metadataResource.data.canGenerateMetadata && client.generateMetadata ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              disabled={pending}
              onClick={() => void generateMetadata()}
              size="xs"
              variant="outline"
            >
              {metadataGenerationStartedAt === undefined
                ? t`Сгенерировать metadata`
                : t`Генерируем metadata…`}
            </Button>
            <Button
              disabled={pending}
              onClick={() => void generateMetadata(true)}
              size="xs"
              variant="outline"
            >
              <Trans>Сгенерировать с типами из таблицы</Trans>
            </Button>
            {metadataGenerationStartedAt === undefined ? (
              <span className="text-caption text-muted-foreground">
                {metadataResource.data.metadataGenerationRequiresConfirmation
                  ? t`Новая генерация полностью заменит таблицу после подтверждения; затем её нужно проверить и сохранить вручную.`
                  : t`Черновик нужно проверить и сохранить вручную.`}
              </span>
            ) : (
              <div
                aria-live="polite"
                className="flex min-w-72 flex-1 items-center gap-2 text-caption text-muted-foreground"
                role="status"
              >
                <LoaderCircle aria-hidden="true" className="size-4 shrink-0 animate-spin" />
                <div className="min-w-48 flex-1 space-y-1">
                  <p>
                    <Trans>
                      Генерируем и перепроверяем metadata. Обычно это занимает 30–60 секунд
                    </Trans>
                    {metadataGenerationElapsedSeconds >= metadataGenerationExpectedSeconds
                      ? t`; запрос всё ещё выполняется: для большого условия это может занять до 10 минут. Не закрывайте страницу.`
                      : '.'}
                  </p>
                  <Progress
                    aria-label={t`Генерация metadata`}
                    value={Math.min(
                      95,
                      (metadataGenerationElapsedSeconds / metadataGenerationExpectedSeconds) * 100,
                    )}
                  />
                </div>
              </div>
            )}
          </div>
        ) : null}
        {message ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>
                <Trans>Не удалось сгенерировать metadata</Trans>
              </AlertTitle>
              <AlertDescription>{message}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {generatedRows ? (
          <Alert tone="success">
            <AlertContent>
              <AlertTitle>
                <Trans>Черновик metadata обновлён</Trans>
              </AlertTitle>
              <AlertDescription>
                <Trans>
                  Результат генерации уже показан в таблице ниже. Проверьте его и нажмите «Сохранить
                  метаданные», чтобы заменить текущую конфигурацию задач.
                </Trans>
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {generationWarnings.length ? (
          <Alert tone="warning">
            <AlertContent>
              <AlertTitle>
                <Trans>Проверьте сгенерированные metadata</Trans>
              </AlertTitle>
              <AlertDescription>{generationWarnings.join(' ')}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {staleDraft ? (
          <Alert tone="warning">
            <AlertContent>
              <AlertTitle>
                <Trans>Серверная версия изменилась</Trans>
              </AlertTitle>
              <AlertDescription>
                <Trans>
                  Черновик не потерян. Сверьте строки с текущими данными перед сохранением.
                </Trans>
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <MetadataGrid
          allowPristineCommit
          columns={metadataColumns}
          commitLabel={t`Сохранить метаданные`}
          disabled={pending}
          {...(draft ? { initialDraftRows: draft.rows } : {})}
          initialRows={baseline}
          key={`${metadataResource.etag}-${metadataGridEpoch}`}
          onCommit={async (rows) => {
            try {
              const saved = await client.saveMetadataGrid({
                groupLessonId,
                revisionId,
                etag: metadataResource.etag,
                rows: metadataMutationRows(rows),
              })
              clearStoredObject(metadataDraftKey)
              acceptMetadata(saved)
              recordProductAction('metadata.change', { type: 'lesson', id: groupLessonId })
            } catch (error) {
              if (error instanceof ApiResponseError && error.status === 409) {
                const current = await client.metadataGrid(groupLessonId, revisionId)
                setMetadataResource(current)
                setStaleDraft(true)
                throw new Error(
                  t`Метаданные уже изменились. Ваш локальный черновик сохранён; обновите и сверьте строки.`,
                )
              }
              throw new Error(readableError(error))
            }
          }}
          onDiscard={() => {
            clearStoredObject(metadataDraftKey)
            metadataRowsRef.current = baseline
            setGeneratedRows(undefined)
            setGenerationWarnings([])
            setMetadataDirty(false)
            setMetadataGridEpoch((epoch) => epoch + 1)
          }}
          onDirtyChange={setMetadataDirty}
          onRowsChange={(rows) => {
            metadataRowsRef.current = rows
            writeStoredObject(metadataDraftKey, {
              schemaVersion: 1,
              etag: metadataResource.etag,
              rows,
            } satisfies StoredMetadataDraft)
          }}
          validate={validateMetadataRows}
        />
      </section>
    )
  }

  return (
    <section className="space-y-3" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <p className="inline-flex items-center gap-1 text-small text-status-success">
          <CheckCircle2 aria-hidden="true" className="size-4" />
          {kind === 'condition'
            ? t`Сопоставление и метаданные подтверждены.`
            : t`Сопоставление задач подтверждено; метаданные берутся из условия.`}
        </p>
        {kind === 'condition' ? (
          <>
            <Button onClick={() => void editMatches()} size="xs" variant="outline">
              <Pencil aria-hidden="true" /> <Trans>Изменить состав задач</Trans>
            </Button>
            <Button onClick={() => void editMetadata()} size="xs" variant="outline">
              <Pencil aria-hidden="true" /> <Trans>Изменить метаданные</Trans>
            </Button>
          </>
        ) : null}
      </div>
      {kind === 'condition' && metadataResource ? (
        <div className="grid gap-2">
          {metadataResource.data.testRechecks.map((row) => (
            <div
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-small"
              key={row.problemPublicId}
            >
              <span>
                <Trans>
                  {row.displayNumber}. {row.title} · ответов: {row.attemptCount}
                </Trans>
                {row.needsRecheck ? (
                  <strong className="ml-2 text-status-warning">
                    <Trans>Требуется перепроверка</Trans>
                  </strong>
                ) : (
                  <span className="ml-2 text-muted-foreground">
                    <Trans>Актуально</Trans>
                  </span>
                )}
              </span>
              <Button
                render={
                  <a
                    aria-label={t`Перепроверить все ответы задачи ${row.displayNumber}`}
                    href={`/staff/problems/${row.problemPublicId}`}
                  />
                }
                size="xs"
                variant="outline"
              >
                <Trans>Перепроверить все ответы</Trans>
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  )
}

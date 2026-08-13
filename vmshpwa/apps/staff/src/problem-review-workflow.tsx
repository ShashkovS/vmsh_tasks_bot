import { CheckCircle2, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { type ContentApiClient, type VersionedContentResource } from '@vmsh/content'
import {
  ApiResponseError,
  answerTypeSchema,
  problemTypeSchema,
  type ContentMaterialKind,
  type ProblemMatchReview,
  type ProblemMetadataGrid,
  type ProblemMetadataMutationRow,
} from '@vmsh/contracts'
import {
  MetadataGrid,
  ProblemMatching,
  type MetadataColumn,
  type MetadataError,
  type MetadataRow,
  type ProblemMatchingSelection,
} from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Button } from '@vmsh/ui'

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

const problemTypeOptions = [
  { value: '1', label: 'Тестовая' },
  { value: '2', label: 'Письменная' },
  { value: '3', label: 'Устная' },
]

const answerTypeOptions = [
  [1, 'Цифра'],
  [2, 'Натуральное число'],
  [3, 'Целое число'],
  [4, 'Отношение'],
  [5, 'Десятичная дробь'],
  [6, 'Обыкновенная или десятичная дробь'],
  [7, 'Последовательность целых'],
  [8, 'Два целых'],
  [9, 'Три целых'],
  [10, 'Четыре целых'],
  [11, 'Множество целых'],
  [12, 'Многочлен'],
  [13, 'Число с точностью'],
  [14, 'Время'],
  [15, 'Дата'],
  [16, 'День недели'],
  [17, 'Последовательность дробей'],
  [18, 'Мультимножество'],
  [19, 'Смешанная дробь'],
  [20, 'Символьное выражение'],
  [21, 'Эквивалентное выражение'],
  [98, 'Выбор одного варианта'],
  [99, 'Строка'],
].map(([value, label]) => ({ value: String(value), label: String(label) }))

const metadataColumns: MetadataColumn[] = [
  { id: 'displayNumber', header: 'Номер', editorClassName: 'w-16 min-w-16' },
  { id: 'title', header: 'Название', editorClassName: 'min-w-56' },
  {
    id: 'problemType',
    header: 'Тип задачи',
    editor: 'select',
    editorClassName: 'min-w-36',
    options: problemTypeOptions,
  },
  {
    id: 'answerType',
    header: 'Тип ответа',
    editor: 'select',
    editorClassName: 'min-w-44 max-w-52',
    options: answerTypeOptions,
  },
  { id: 'answerValidation', header: 'Своя валидация', editor: 'textarea' },
  { id: 'validationError', header: 'Ошибка формата', editor: 'textarea' },
  { id: 'correctAnswer', header: 'Правильный ответ', editor: 'textarea' },
  { id: 'correctAnswerChecker', header: 'Проверяльщик', editor: 'textarea' },
  { id: 'wrongAnswer', header: 'Неверный ответ', editor: 'textarea' },
  { id: 'congratulation', header: 'Верный ответ', editor: 'textarea' },
]

const typeLabels: Record<number, string> = {
  1: 'тестовая',
  2: 'письменная',
  3: 'устная',
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
      errors.push({ row: index, col: 'title', message: 'Заполните короткое название задачи' })
    }
    if (!problemTypeOptions.some((option) => option.value === row.problemType)) {
      errors.push({ row: index, col: 'problemType', message: 'Выберите тип задачи' })
    }
    if (
      row.problemType === '1' &&
      !answerTypeOptions.some((item) => item.value === row.answerType)
    ) {
      errors.push({
        row: index,
        col: 'answerType',
        message: 'Для тестовой задачи нужен тип ответа',
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
            message: 'Поля ответа доступны только для тестовой задачи',
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
  return 'Не удалось загрузить проверку задач'
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
      if (resource.data.rows.every((row) => row.reviewed)) {
        clearStoredObject(metadataDraftKey)
        setPhase('ready')
        return
      }
      const draft = storedMetadataRows(metadataDraftKey, resource.data)
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
            'Структура задач или пунктов не совпадает с условием. Исправьте LaTeX-файл и загрузите новую revision.',
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

  useEffect(() => {
    const task = globalThis.setTimeout(() => void reload(), 0)
    return () => globalThis.clearTimeout(task)
  }, [reload])

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
        typeLabel: typeLabels[candidate.problemType] ?? `тип ${candidate.problemType}`,
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
        if (!selection) throw new Error('Выберите действие для каждой задачи')
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
            'Сервер уже принял другое изменение. Текущее состояние загружено заново; проверьте только строки, которые нельзя сопоставить автоматически.',
          )
        }
      } else {
        setMessage(readableError(error))
      }
    } finally {
      setPending(false)
    }
  }

  if (phase === 'loading') {
    return <p className="text-small text-muted-foreground">Загружаем структуру задач…</p>
  }

  if (phase === 'error') {
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>Не удалось загрузить проверку задач</AlertTitle>
          <AlertDescription>{message}</AlertDescription>
          <Button className="mt-2" onClick={() => void reload()} size="xs" variant="outline">
            <RefreshCw aria-hidden="true" /> Повторить
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
    const draft = storedMetadataRows(metadataDraftKey, metadataResource.data)
    return (
      <section aria-labelledby={`problem-metadata-${kind}`} className="space-y-2">
        <div>
          <h3 className="text-small font-semibold" id={`problem-metadata-${kind}`}>
            Метаданные задач
          </h3>
          <p className="text-caption text-muted-foreground">
            Проверьте названия, способы сдачи и сообщения проверки. Таблица сохраняется локально до
            подтверждения.
          </p>
        </div>
        {staleDraft ? (
          <Alert tone="warning">
            <AlertContent>
              <AlertTitle>Серверная версия изменилась</AlertTitle>
              <AlertDescription>
                Черновик не потерян. Сверьте строки с текущими данными перед сохранением.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <MetadataGrid
          columns={metadataColumns}
          {...(draft ? { initialDraftRows: draft.rows } : {})}
          initialRows={baseline}
          key={metadataResource.etag}
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
            } catch (error) {
              if (error instanceof ApiResponseError && error.status === 409) {
                const current = await client.metadataGrid(groupLessonId, revisionId)
                setMetadataResource(current)
                setStaleDraft(true)
                throw new Error(
                  'Метаданные уже изменились. Ваш локальный черновик сохранён; обновите и сверьте строки.',
                )
              }
              throw new Error(readableError(error))
            }
          }}
          onDiscard={() => clearStoredObject(metadataDraftKey)}
          onRowsChange={(rows) =>
            writeStoredObject(metadataDraftKey, {
              schemaVersion: 1,
              etag: metadataResource.etag,
              rows,
            } satisfies StoredMetadataDraft)
          }
          validate={validateMetadataRows}
        />
      </section>
    )
  }

  return (
    <p className="inline-flex items-center gap-1 text-small text-status-success" role="status">
      <CheckCircle2 aria-hidden="true" className="size-4" />
      {kind === 'condition'
        ? 'Сопоставление и метаданные подтверждены.'
        : 'Сопоставление задач подтверждено; метаданные берутся из условия.'}
    </p>
  )
}

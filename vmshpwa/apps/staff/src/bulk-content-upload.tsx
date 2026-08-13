import { AlertTriangle, CheckCircle2, Files, LoaderCircle, X } from 'lucide-react'
import { useMemo, useState } from 'react'

import { type ContentApiClient, useContentUploadTargetsQuery } from '@vmsh/content'
import {
  ApiResponseError,
  type ContentMaterialKind,
  type ContentUploadTarget,
} from '@vmsh/contracts'
import { LevelChip, type GroupView } from '@vmsh/product'
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

import {
  type BulkContentUploadRow,
  type BulkContentMaterialKind,
  bulkContentRecoveryHref,
  createBulkContentUploadRows,
  validateBulkContentUploadRows,
} from './bulk-content-upload-model'
import { stableBrowserFile } from './stable-browser-file'

const materialLabels: Record<BulkContentMaterialKind, string> = {
  condition: 'Условие',
  hint: 'Подсказка',
  solution: 'Решение',
  hint_solution: 'Подсказки и решения',
}

function colorIndex(colorKey: string | null): GroupView['colorIndex'] {
  const match = /^level-([1-4])$/.exec(colorKey ?? '')
  return match ? (Number(match[1]) as GroupView['colorIndex']) : 0
}

function groupView(target: ContentUploadTarget, courseId: string): GroupView {
  return {
    id: target.groupId,
    courseId,
    code: target.groupShortCode,
    name: target.groupName,
    colorIndex: colorIndex(target.colorKey),
  }
}

function rowStatus(row: BulkContentUploadRow) {
  switch (row.phase) {
    case 'uploading':
      return <Badge variant="info">Загружаем</Badge>
    case 'compiling':
      return <Badge variant="info">Проверяем</Badge>
    case 'ready':
      return <Badge variant="success">Готово</Badge>
    case 'attention':
      return <Badge variant="warning">Требует внимания</Badge>
    default:
      return <Badge variant="neutral">Ожидает</Badge>
  }
}

export function BulkContentUpload({
  client,
  groupLessonId,
  onCompleted,
}: {
  client: ContentApiClient
  groupLessonId: string
  onCompleted: () => Promise<unknown>
}) {
  const targetsQuery = useContentUploadTargetsQuery(client, groupLessonId)
  const [rows, setRows] = useState<BulkContentUploadRow[]>([])
  const [running, setRunning] = useState(false)
  const [batchError, setBatchError] = useState<string>()
  const targets = useMemo(() => targetsQuery.data?.targets ?? [], [targetsQuery.data?.targets])
  const validationMessage = useMemo(
    () => (rows.length > 0 ? validateBulkContentUploadRows(rows, targets) : undefined),
    [rows, targets],
  )

  const updateRow = (id: string, update: Partial<BulkContentUploadRow>) => {
    setRows((current) => current.map((row) => (row.id === id ? { ...row, ...update } : row)))
  }

  const runBatch = async () => {
    if (running || validationMessage || rows.length === 0) return
    setRunning(true)
    setBatchError(undefined)
    try {
      // Serial execution is intentional: one weekly batch is small, while
      // concurrent TeX/PDF subprocesses add load without improving the admin's
      // decision flow. See Phase 2 bulk upload in 06-phase-2-content.md.
      for (const row of rows) {
        try {
          const kinds: ContentMaterialKind[] =
            row.kind === 'hint_solution' ? ['hint', 'solution'] : [row.kind]
          for (const kind of kinds) {
            updateRow(row.id, { phase: 'uploading', message: undefined })
            const uploaded = await client.uploadSource({
              groupLessonId: row.groupLessonId,
              kind,
              logicalFilename: row.file.name,
              source: row.file,
            })
            updateRow(row.id, { phase: 'compiling', revisionId: uploaded.data.revisionId })
            const compiled = await client.compileRevision(uploaded.data.revisionId, uploaded.etag)
            if (compiled.data.status !== 'ready') {
              throw new Error('Revision сохранена, но требует отдельной проверки.')
            }
          }
          updateRow(row.id, { phase: 'ready', message: undefined })
        } catch (error) {
          updateRow(row.id, {
            phase: 'attention',
            message:
              error instanceof ApiResponseError && error.code === 'content_assets_missing'
                ? 'Файл сохранён. Откройте занятие и добавьте недостающие рисунки.'
                : error instanceof Error
                  ? error.message
                  : 'Не удалось обработать файл.',
          })
        }
      }
      try {
        await onCompleted()
      } catch {
        setBatchError(
          'Файлы обработаны, но историю материалов не удалось обновить. Обновите страницу.',
        )
      }
    } finally {
      setRunning(false)
    }
  }

  const readyCount = rows.filter((row) => row.phase === 'ready').length
  const attentionCount = rows.filter((row) => row.phase === 'attention').length

  return (
    <Card>
      <CardHeader className="gap-1">
        <CardTitle className="flex items-center gap-2" aria-level={2} role="heading">
          <Files aria-hidden="true" />
          Массовая загрузка
        </CardTitle>
        <p className="text-small text-muted-foreground">
          Выберите несколько файлов и укажите группу. По умолчанию это условия; при необходимости
          вид материала можно изменить. Загрузка ничего не публикует.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {targetsQuery.isPending ? (
          <p className="text-small text-muted-foreground" role="status">
            Загружаем группы занятия…
          </p>
        ) : targetsQuery.error ? (
          <Alert tone="danger">
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Не удалось получить группы занятия</AlertTitle>
              <AlertDescription>
                <Button onClick={() => void targetsQuery.refetch()} size="xs" variant="outline">
                  Повторить
                </Button>
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : (
          <p className="text-caption text-muted-foreground">
            {targetsQuery.data.courseName} · занятие {targetsQuery.data.lessonNumber} · групп:{' '}
            {targets.length}
          </p>
        )}

        <div className="space-y-1">
          <Label htmlFor="bulk-content-files">LaTeX-файлы</Label>
          <Input
            accept=".tex,text/plain,application/x-tex"
            disabled={running || targetsQuery.isPending || Boolean(targetsQuery.error)}
            id="bulk-content-files"
            multiple
            onChange={(event) => {
              const selected = Array.from(event.currentTarget.files ?? [])
              void Promise.all(selected.map(stableBrowserFile)).then(
                (files) => setRows(createBulkContentUploadRows(files)),
                () =>
                  setBatchError(
                    'Не удалось прочитать один из выбранных файлов. Скопируйте его на локальный диск и выберите набор ещё раз.',
                  ),
              )
            }}
            type="file"
          />
        </div>

        {rows.length > 0 ? (
          <div className="space-y-2" aria-label="Сопоставление файлов">
            {rows.map((row, index) => {
              const groupLabelId = `${row.id}-group-label`
              const kindLabelId = `${row.id}-kind-label`
              const selectedTarget = targets.find(
                (target) => target.groupLessonId === row.groupLessonId,
              )
              const recoveryHref = bulkContentRecoveryHref(row)
              return (
                <div
                  className="grid min-w-0 gap-2 rounded-md border border-border bg-surface-subtle p-2 lg:grid-cols-[minmax(12rem,1fr)_minmax(12rem,16rem)_minmax(10rem,13rem)_auto] lg:items-center"
                  key={row.id}
                >
                  <div className="min-w-0">
                    <p className="truncate text-small font-medium" title={row.file.name}>
                      {index + 1}. {row.file.name}
                    </p>
                    <p className="text-caption text-muted-foreground">
                      {Math.max(1, Math.ceil(row.file.size / 1024))} КБ
                    </p>
                  </div>
                  <div className="min-w-0 space-y-1">
                    <span className="sr-only" id={groupLabelId}>
                      Группа для файла {row.file.name}
                    </span>
                    <Select
                      disabled={running}
                      onValueChange={(value) => updateRow(row.id, { groupLessonId: value ?? '' })}
                      value={row.groupLessonId || null}
                    >
                      <SelectTrigger aria-labelledby={groupLabelId} className="w-full" size="sm">
                        <SelectValue placeholder="Выберите группу">
                          {selectedTarget ? (
                            <>
                              <LevelChip
                                compact
                                level={groupView(
                                  selectedTarget,
                                  targetsQuery.data?.courseId ?? 'course',
                                )}
                              />
                              {selectedTarget.groupName}
                            </>
                          ) : undefined}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent align="start">
                        {targets.map((target) => (
                          <SelectItem
                            disabled={target.status === 'archived'}
                            key={target.groupLessonId}
                            value={target.groupLessonId}
                          >
                            <LevelChip
                              compact
                              level={groupView(target, targetsQuery.data?.courseId ?? 'course')}
                            />
                            {target.groupName}
                            {target.status === 'archived' ? ' · архив' : ''}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="min-w-0 space-y-1">
                    <span className="sr-only" id={kindLabelId}>
                      Вид материала для файла {row.file.name}
                    </span>
                    <Select
                      disabled={running}
                      onValueChange={(value) =>
                        updateRow(row.id, {
                          kind: value && value in materialLabels ? value : 'condition',
                        })
                      }
                      value={row.kind || null}
                    >
                      <SelectTrigger aria-labelledby={kindLabelId} className="w-full" size="sm">
                        <SelectValue placeholder="Вид материала">
                          {row.kind ? materialLabels[row.kind] : undefined}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent align="start">
                        {(Object.keys(materialLabels) as BulkContentMaterialKind[]).map((kind) => (
                          <SelectItem key={kind} value={kind}>
                            {materialLabels[kind]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center justify-between gap-2 lg:justify-end">
                    {rowStatus(row)}
                    <Button
                      aria-label={`Убрать файл ${row.file.name}`}
                      disabled={running}
                      onClick={() =>
                        setRows((current) => current.filter((item) => item.id !== row.id))
                      }
                      size="icon-xs"
                      variant="ghost"
                    >
                      <X aria-hidden="true" />
                    </Button>
                  </div>
                  {row.message ? (
                    <div
                      className="flex flex-wrap items-center gap-2 text-caption text-status-warning lg:col-span-4"
                      role="status"
                    >
                      <span>{row.message}</span>
                      {recoveryHref ? (
                        <a className="font-medium underline underline-offset-2" href={recoveryHref}>
                          Открыть недостающие рисунки
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        ) : null}

        {validationMessage ? (
          <p className="text-small text-status-danger" role="alert">
            {validationMessage}
          </p>
        ) : null}

        {batchError ? (
          <p className="text-small text-status-danger" role="alert">
            {batchError}
          </p>
        ) : null}

        {readyCount > 0 || attentionCount > 0 ? (
          <p className="flex items-center gap-2 text-small" role="status">
            {attentionCount > 0 ? (
              <AlertTriangle aria-hidden="true" className="text-status-warning" />
            ) : (
              <CheckCircle2 aria-hidden="true" className="text-status-success" />
            )}
            Готово: {readyCount} · требуют внимания: {attentionCount}
          </p>
        ) : null}

        {attentionCount > 0 ? (
          <Alert tone="warning">
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Загрузка сохранена, но нужны рисунки</AlertTitle>
              <AlertDescription>
                Откройте нужное занятие по ссылке у файла, загрузите отсутствующий внешний рисунок и
                повторите сборку материала. TikZ обрабатывается автоматически.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={running || rows.length === 0 || Boolean(validationMessage)}
            onClick={() => void runBatch()}
            size="sm"
          >
            {running ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" />
            ) : (
              <Files aria-hidden="true" />
            )}
            {running ? 'Обрабатываем набор…' : 'Загрузить набор и проверить'}
          </Button>
          {rows.length > 0 ? (
            <Button disabled={running} onClick={() => setRows([])} size="sm" variant="ghost">
              Очистить список
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

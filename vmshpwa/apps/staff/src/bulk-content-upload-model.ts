import {
  ApiResponseError,
  type ContentDiagnostic,
  type ContentMaterialKind,
  type ContentUploadTarget,
} from '@vmsh/contracts'

const SOURCE_LIMIT_BYTES = 512 * 1024
const MAX_BATCH_FILES = 100

type BulkUploadRowPhase = 'queued' | 'uploading' | 'compiling' | 'ready' | 'attention'
export type BulkContentMaterialKind = ContentMaterialKind | 'hint_solution'

export interface BulkContentUploadRow {
  id: string
  file: File
  groupLessonId: string
  kind: BulkContentMaterialKind
  revisionId: string | undefined
  phase: BulkUploadRowPhase
  message: string | undefined
  diagnostics: ContentDiagnostic[] | undefined
  missingAssets: string[] | undefined
}

export function createBulkContentUploadRows(files: readonly File[]): BulkContentUploadRow[] {
  return files.map((file, index) => ({
    id: `bulk-${index}-${file.name}-${file.size}`,
    file,
    groupLessonId: '',
    kind: /-sol\.tex$/iu.test(file.name) ? 'hint_solution' : 'condition',
    revisionId: undefined,
    phase: 'queued',
    message: undefined,
    diagnostics: undefined,
    missingAssets: undefined,
  }))
}

export function validateBulkContentUploadRows(
  rows: readonly BulkContentUploadRow[],
  targets: readonly ContentUploadTarget[],
): string | undefined {
  if (rows.length === 0) return 'Выберите хотя бы один LaTeX-файл.'
  if (rows.length > MAX_BATCH_FILES)
    return `За один раз можно загрузить не больше ${MAX_BATCH_FILES} файлов.`
  const targetIds = new Set(
    targets.filter((target) => target.status !== 'archived').map((target) => target.groupLessonId),
  )
  const slots = new Set<string>()
  for (const row of rows) {
    if (!row.file.name.toLocaleLowerCase('ru-RU').endsWith('.tex')) {
      return `Файл «${row.file.name}» должен иметь расширение .tex.`
    }
    if (row.file.size === 0) return `Файл «${row.file.name}» пуст.`
    if (row.file.size > SOURCE_LIMIT_BYTES) return `Файл «${row.file.name}» больше 512 КБ.`
    if (!row.groupLessonId || !targetIds.has(row.groupLessonId)) {
      return `Выберите действующую группу для файла «${row.file.name}».`
    }
    const materialKinds: ContentMaterialKind[] =
      row.kind === 'hint_solution' ? ['hint', 'solution'] : [row.kind]
    for (const kind of materialKinds) {
      const slot = `${row.groupLessonId}:${kind}`
      if (slots.has(slot)) return 'Одна группа и вид материала выбраны для нескольких файлов.'
      slots.add(slot)
    }
  }
  return undefined
}

export function bulkContentRecoveryHref(row: BulkContentUploadRow): string | undefined {
  if (row.phase !== 'attention' || !row.groupLessonId) return undefined
  if (row.kind === 'hint_solution') {
    return `/staff/lessons/${encodeURIComponent(row.groupLessonId)}`
  }
  return `/staff/lessons/${encodeURIComponent(row.groupLessonId)}#material-${row.kind}`
}

export function bulkContentRevisionId(error: unknown): string | undefined {
  if (!(error instanceof ApiResponseError)) return undefined
  const revisionId = error.details?.revisionId
  return typeof revisionId === 'string' ? revisionId : undefined
}

export function bulkContentUploadErrorMessage(error: unknown): string {
  if (!(error instanceof ApiResponseError)) {
    return error instanceof Error ? error.message : 'Не удалось обработать файл.'
  }
  if (error.code === 'content_assets_missing') {
    return 'Файл сохранён. Откройте занятие и добавьте недостающие рисунки.'
  }
  if (error.code !== 'asset_conversion_failed' && error.code !== 'content_assets_unavailable') {
    return error.message
  }

  const reason = error.details?.reason
  const reasonMessage =
    reason === 'asset.converter_timeout'
      ? 'Сборка рисунка превысила лимит времени.'
      : reason === 'asset.tikz_forbidden_command'
        ? 'В TikZ есть запрещённая файловая или исполняемая команда.'
        : reason === 'asset.tikz_document_boundary'
          ? 'В TikZ-фрагмент попали команды начала или конца документа.'
          : reason === 'asset.tool_unavailable' || reason === 'asset.converter_start_failed'
            ? 'На сервере временно недоступен инструмент обработки рисунков.'
            : 'LaTeX-компилятор не смог безопасно собрать рисунок.'
  const logicalAsset = error.details?.logicalAsset
  const detail = error.details?.detail
  return [
    reasonMessage,
    typeof logicalAsset === 'string' ? `Рисунок: ${logicalAsset}.` : undefined,
    typeof detail === 'string' && detail.trim() ? `Причина: ${detail}` : undefined,
  ]
    .filter(Boolean)
    .join(' ')
}

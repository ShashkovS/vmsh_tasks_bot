import type { ContentMaterialKind, ContentUploadTarget } from '@vmsh/contracts'

const SOURCE_LIMIT_BYTES = 512 * 1024
const MAX_BATCH_FILES = 100

type BulkUploadRowPhase = 'queued' | 'uploading' | 'compiling' | 'ready' | 'attention'

export interface BulkContentUploadRow {
  id: string
  file: File
  groupLessonId: string
  kind: ContentMaterialKind | ''
  phase: BulkUploadRowPhase
  message: string | undefined
}

export function createBulkContentUploadRows(files: readonly File[]): BulkContentUploadRow[] {
  return files.map((file, index) => ({
    id: `bulk-${index}-${file.name}-${file.size}`,
    file,
    groupLessonId: '',
    kind: '',
    phase: 'queued',
    message: undefined,
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
    if (!row.kind) return `Выберите вид материала для файла «${row.file.name}».`
    const slot = `${row.groupLessonId}:${row.kind}`
    if (slots.has(slot)) return 'Одна группа и вид материала выбраны для нескольких файлов.'
    slots.add(slot)
  }
  return undefined
}

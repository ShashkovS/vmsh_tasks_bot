import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useEffect, useMemo, useState, type ClipboardEvent } from 'react'
import { Copy, Maximize2, Minimize2, Redo2, Undo2 } from 'lucide-react'

import { Button, Dialog, DialogContent, DialogHeader, DialogTitle, cn } from '@vmsh/ui'

import {
  hasMetadataHeaders,
  matrixFromRows,
  normalizeClipboardValue,
  parseMetadataTsv,
  serializeMetadataTsv,
} from './metadata-grid-clipboard'
import { MetadataGridCellEditor } from './metadata-grid-cell-editor'
import {
  applyEdit,
  applyNewEdit,
  cellRange,
  cloneRows,
  commitModel,
  createCellEdit,
  pasteEdit,
  redoModel,
  resetModel,
  rowsEqual,
  undoModel,
} from './metadata-grid-model'
import { MetadataGridTable } from './metadata-grid-table'
import type {
  CellAddress,
  GridEdit,
  GridModel,
  MetadataColumn,
  MetadataError,
  MetadataGridProps,
  MetadataRow,
} from './metadata-grid-types'

export type {
  MetadataColumn,
  MetadataError,
  MetadataGridProps,
  MetadataRow,
} from './metadata-grid-types'

function initialModel(initialRows: MetadataRow[], initialDraftRows?: MetadataRow[]): GridModel {
  const rows = cloneRows(initialDraftRows ?? initialRows)
  return {
    baseline: cloneRows(initialRows),
    rows,
    selection: rows.length ? { anchor: { row: 0, col: 0 }, focus: { row: 0, col: 0 } } : null,
    undo: [],
    redo: [],
  }
}

function selectErrors(rows: MetadataRow[], columns: MetadataColumn[]): MetadataError[] {
  return rows.flatMap((row, rowIndex) =>
    columns.flatMap((column) => {
      const value = row[column.id] ?? ''
      if (!column.options || !value || column.options.some((option) => option.value === value)) {
        return []
      }
      return [
        {
          row: rowIndex,
          col: column.id,
          message: t`Выберите допустимое значение «${column.header}»`,
        },
      ]
    }),
  )
}

function allErrors(
  rows: MetadataRow[],
  columns: MetadataColumn[],
  validate?: (rows: MetadataRow[]) => MetadataError[],
): MetadataError[] {
  const unique = new Map<string, MetadataError>()
  for (const error of [...selectErrors(rows, columns), ...(validate?.(rows) ?? [])]) {
    unique.set(`${error.row}:${error.col}:${error.message}`, error)
  }
  return [...unique.values()]
}

function formatClipboardError(reason: string): string {
  if (reason === 'quotes') return t`Не удалось вставить таблицу: в данных незакрытая кавычка.`
  if (reason === 'shape')
    return t`Не удалось вставить таблицу: все строки должны содержать одинаковое число ячеек.`
  if (reason === 'empty') return t`В буфере нет значений для вставки.`
  if (reason === 'bounds') return t`Фрагмент не помещается в таблицу. Данные не были изменены.`
  return t`Не удалось вставить таблицу.`
}

/** Spreadsheet-like editor for the Staff condition-review metadata flow. */
export function MetadataGrid({
  allowPristineCommit = false,
  columns,
  initialRows,
  initialDraftRows,
  validate,
  onRowsChange,
  onDiscard,
  onCommit,
  onDirtyChange,
  className,
  commitLabel,
  title,
  disabled = false,
}: MetadataGridProps) {
  const [model, setModel] = useState(() => initialModel(initialRows, initialDraftRows))
  const [errors, setErrors] = useState<MetadataError[]>([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string>()
  const [clipboardError, setClipboardError] = useState<string>()
  const [validationSucceeded, setValidationSucceeded] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [editing, setEditing] = useState<{ address: CellAddress; initialValue?: string }>()
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    Object.fromEntries(columns.map((column) => [column.id, column.width ?? 180])),
  )

  const gridTitle = title ?? t`Метаданные задач`
  const commitText = commitLabel ?? t`Сохранить`

  const dirty = !rowsEqual(model.rows, model.baseline)
  const interactionDisabled = disabled || saving
  const editingCell = editing
    ? {
        ...editing,
        column: columns[editing.address.col],
        row: model.rows[editing.address.row],
      }
    : undefined

  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])

  const visibleMatrix = useMemo(() => matrixFromRows(model.rows, columns), [columns, model.rows])
  const notifyRows = (rows: MetadataRow[]) => onRowsChange?.(rows)

  const applyGridEdit = (edit: GridEdit | null) => {
    if (!edit || interactionDisabled) return
    const rows = applyEdit(model.rows, edit, 'redo')
    setModel((current) => applyNewEdit(current, edit))
    notifyRows(rows)
    setErrors(allErrors(rows, columns, validate))
    setValidationSucceeded(false)
    setSaveError(undefined)
    setClipboardError(undefined)
  }

  const runDryRun = () => {
    const nextErrors = allErrors(model.rows, columns, validate)
    setErrors(nextErrors)
    setValidationSucceeded(nextErrors.length === 0)
    setClipboardError(undefined)
  }

  const undo = () => {
    if (!model.undo.length || interactionDisabled) return
    const next = undoModel(model)
    setModel(next)
    notifyRows(next.rows)
    setErrors(allErrors(next.rows, columns, validate))
    setValidationSucceeded(false)
  }

  const redo = () => {
    if (!model.redo.length || interactionDisabled) return
    const next = redoModel(model)
    setModel(next)
    notifyRows(next.rows)
    setErrors(allErrors(next.rows, columns, validate))
    setValidationSucceeded(false)
  }

  const discard = () => {
    if (!dirty || interactionDisabled) return
    const next = resetModel(model)
    setModel(next)
    notifyRows(next.rows)
    setErrors([])
    setSaveError(undefined)
    setClipboardError(undefined)
    setValidationSucceeded(false)
    onDiscard?.()
  }

  const save = async () => {
    const nextErrors = allErrors(model.rows, columns, validate)
    setErrors(nextErrors)
    if (nextErrors.length) return
    setSaving(true)
    setSaveError(undefined)
    try {
      await onCommit?.(model.rows)
      setModel((current) => commitModel(current))
      setErrors([])
      setValidationSucceeded(false)
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : t`Не удалось сохранить изменения`)
    } finally {
      setSaving(false)
    }
  }

  const copyAll = async () => {
    const text = serializeMetadataTsv(matrixFromRows(model.rows, columns, true))
    try {
      await globalThis.navigator.clipboard.writeText(text)
      setClipboardError(undefined)
    } catch {
      setClipboardError(t`Браузер не дал доступ к буферу. Выделите таблицу и нажмите Ctrl/Cmd+C.`)
    }
  }

  const copySelection = (event: ClipboardEvent<HTMLTableElement>) => {
    if (!model.selection) return
    const range = cellRange(model.selection)
    const text = serializeMetadataTsv(
      visibleMatrix
        .slice(range.firstRow, range.lastRow + 1)
        .map((row) => row.slice(range.firstCol, range.lastCol + 1)),
    )
    event.preventDefault()
    event.clipboardData.setData('text/plain', text)
  }

  const paste = (event: ClipboardEvent<HTMLTableElement>) => {
    if (interactionDisabled || !model.selection) return
    const text = event.clipboardData.getData('text/plain')
    if (!text) return
    event.preventDefault()
    const parsed = parseMetadataTsv(text)
    if (!parsed.ok) {
      setClipboardError(formatClipboardError(parsed.reason))
      return
    }
    const start = model.selection.focus
    const values =
      start.row === 0 && start.col === 0 && hasMetadataHeaders(parsed.rows[0]!, columns)
        ? parsed.rows.slice(1)
        : parsed.rows
    if (!values.length || !values[0]?.length) {
      setClipboardError(formatClipboardError('empty'))
      return
    }
    if (
      start.row + values.length > model.rows.length ||
      start.col + values[0].length > columns.length
    ) {
      setClipboardError(formatClipboardError('bounds'))
      return
    }
    const normalized = values.map((line) =>
      line.map((value, offset) => normalizeClipboardValue(value, columns[start.col + offset]!)),
    )
    applyGridEdit(pasteEdit(model.rows, columns, start, normalized, model.selection))
  }

  const clearSelection = () => {
    if (!model.selection || interactionDisabled) return
    const range = cellRange(model.selection)
    const values = Array.from({ length: range.lastRow - range.firstRow + 1 }, () =>
      Array.from({ length: range.lastCol - range.firstCol + 1 }, () => ''),
    )
    applyGridEdit(
      pasteEdit(
        model.rows,
        columns,
        { row: range.firstRow, col: range.firstCol },
        values,
        model.selection,
      ),
    )
  }

  const keyboardUndoRedo = (event: React.KeyboardEvent<HTMLTableElement>) => {
    if (!(event.metaKey || event.ctrlKey) || event.altKey) return
    const key = event.key.toLocaleLowerCase('ru')
    if (key === 'z') {
      event.preventDefault()
      if (event.shiftKey) redo()
      else undo()
    } else if (key === 'y') {
      event.preventDefault()
      redo()
    }
  }

  const table = (tableClassName?: string, wrapperClassName?: string) => (
    <div className={wrapperClassName}>
      <MetadataGridTable
        {...(tableClassName ? { className: tableClassName } : {})}
        columns={columns}
        disabled={interactionDisabled}
        errors={errors}
        onClearSelection={clearSelection}
        onCopy={copySelection}
        onGridKeyDown={keyboardUndoRedo}
        onOpenCell={(address) => setEditing({ address })}
        onPaste={paste}
        onResize={(column, width) => setWidths((current) => ({ ...current, [column.id]: width }))}
        onSelectionChange={(selection) => setModel((current) => ({ ...current, selection }))}
        onStartTyping={(address, value) => setEditing({ address, initialValue: value })}
        rows={model.rows}
        selection={model.selection}
        widths={widths}
      />
    </div>
  )

  const actions = (compact = false) => (
    <div className={cn('flex flex-wrap items-center gap-2', compact && 'justify-end')}>
      <Button
        disabled={!model.rows.length}
        onClick={() => void copyAll()}
        size="sm"
        variant="outline"
      >
        <Copy aria-hidden="true" /> <Trans>Копировать всю таблицу</Trans>
      </Button>
      <Button
        disabled={!model.undo.length || interactionDisabled}
        onClick={undo}
        size="sm"
        variant="outline"
      >
        <Undo2 aria-hidden="true" /> <Trans>Отменить</Trans>
      </Button>
      <Button
        disabled={!model.redo.length || interactionDisabled}
        onClick={redo}
        size="sm"
        variant="outline"
      >
        <Redo2 aria-hidden="true" /> <Trans>Повторить</Trans>
      </Button>
      <Button onClick={runDryRun} size="sm" variant="outline">
        <Trans>Проверить таблицу</Trans>
      </Button>
      <Button disabled={!dirty || interactionDisabled} onClick={discard} size="sm" variant="ghost">
        <Trans>Отменить правки</Trans>
      </Button>
      <Button
        disabled={
          (!dirty && !allowPristineCommit) || errors.length > 0 || interactionDisabled || !!editing
        }
        onClick={() => void save()}
        size="sm"
      >
        {saving ? t`Сохраняем…` : commitText}
      </Button>
    </div>
  )

  const messages = (
    <>
      {clipboardError ? (
        <p className="text-small text-status-danger" role="alert">
          {clipboardError}
        </p>
      ) : null}
      {errors.length > 0 ? (
        <ul className="space-y-1 text-small text-status-danger" role="alert">
          {errors.map((error, index) => {
            const column = columns.find((item) => item.id === error.col)
            return (
              <li key={`${error.row}-${error.col}-${index}`}>
                <button
                  className="text-left underline underline-offset-2"
                  onClick={() => {
                    const col = columns.findIndex((item) => item.id === error.col)
                    if (col < 0) return
                    const address = { row: error.row, col }
                    setModel((current) => ({
                      ...current,
                      selection: { anchor: address, focus: address },
                    }))
                    setEditing({ address })
                  }}
                  type="button"
                >
                  <Trans>Строка</Trans> {error.row + 1}, «{column?.header}»: {error.message}
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
      {validationSucceeded ? (
        <p className="text-small text-status-success" role="status">
          <Trans>Ошибок не найдено. Можно подтверждать метаданные.</Trans>
        </p>
      ) : null}
      {saveError ? (
        <p className="text-small text-status-danger" role="alert">
          {saveError}
        </p>
      ) : null}
    </>
  )

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-caption text-muted-foreground">
          <Trans>
            Выделяйте диапазон мышью или Shift+стрелками. Можно вставить и скопировать TSV из
            таблицы.
          </Trans>
        </p>
        <Button onClick={() => setFullscreen(true)} size="sm" variant="outline">
          <Maximize2 aria-hidden="true" /> <Trans>На весь экран</Trans>
        </Button>
      </div>
      {table('max-h-[min(60dvh,40rem)]')}
      {actions()}
      {messages}

      <Dialog onOpenChange={setFullscreen} open={fullscreen}>
        <DialogContent
          className="flex h-dvh w-screen max-w-none flex-col gap-3 rounded-none p-4 sm:max-w-none"
          showCloseButton={false}
        >
          <DialogHeader className="flex-row items-center justify-between gap-4">
            <DialogTitle>{gridTitle}</DialogTitle>
            <Button onClick={() => setFullscreen(false)} size="sm" variant="outline">
              <Minimize2 aria-hidden="true" /> <Trans>Свернуть</Trans>
            </Button>
          </DialogHeader>
          {table('flex-1', 'min-h-0 flex flex-1 flex-col')}
          {messages}
          {actions(true)}
        </DialogContent>
      </Dialog>

      {editingCell?.column && editingCell.row ? (
        <MetadataGridCellEditor
          column={editingCell.column}
          displayNumber={editingCell.row.displayNumber ?? ''}
          initialValue={editingCell.initialValue ?? editingCell.row[editingCell.column.id] ?? ''}
          onApply={(value) => {
            const edit = createCellEdit(
              model.rows,
              columns,
              editingCell.address.row,
              editingCell.address.col,
              value,
              model.selection,
              { anchor: editingCell.address, focus: editingCell.address },
            )
            setEditing(undefined)
            applyGridEdit(edit)
          }}
          onClose={() => setEditing(undefined)}
        />
      ) : null}
    </div>
  )
}

import { useState, type ClipboardEvent } from 'react'

import { Button, Input, cn } from '@vmsh/ui'

/*
 * Editable metadata grid. Cells edit in place; a rectangular TSV fragment can be
 * pasted starting at the focused cell; a dry-run validates before committing;
 * «Отменить правки» is a single undo boundary back to the last saved state.
 */
export interface MetadataColumn {
  id: string
  header: string
  editor?: 'text' | 'select'
  options?: { value: string; label: string }[]
}

export interface MetadataError {
  row: number
  col: string
  message: string
}

export type MetadataRow = Record<string, string>

export interface MetadataGridProps {
  columns: MetadataColumn[]
  initialRows: MetadataRow[]
  initialDraftRows?: MetadataRow[]
  validate?: (rows: MetadataRow[]) => MetadataError[]
  onRowsChange?: (rows: MetadataRow[]) => void
  onDiscard?: () => void
  onCommit?: (rows: MetadataRow[]) => void | Promise<void>
  className?: string
}

export function MetadataGrid({
  columns,
  initialRows,
  initialDraftRows,
  validate,
  onRowsChange,
  onDiscard,
  onCommit,
  className,
}: MetadataGridProps) {
  const [rows, setRows] = useState<MetadataRow[]>(initialDraftRows ?? initialRows)
  const [baseline, setBaseline] = useState<MetadataRow[]>(initialRows)
  const [errors, setErrors] = useState<MetadataError[]>([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string>()
  const dirty = rows !== baseline

  const setCell = (rowIndex: number, colId: string, value: string) => {
    setErrors([])
    setSaveError(undefined)
    const next = rows.map((row, index) => (index === rowIndex ? { ...row, [colId]: value } : row))
    setRows(next)
    onRowsChange?.(next)
  }

  const handlePaste = (event: ClipboardEvent<HTMLElement>, rowIndex: number, colIndex: number) => {
    const text = event.clipboardData.getData('text')
    if (!text.includes('\t') && !text.includes('\n')) return
    event.preventDefault()
    setErrors([])
    const grid = text
      .replace(/\r/g, '')
      .split('\n')
      .map((line) => line.split('\t'))
    const next = rows.map((row) => ({ ...row }))
    grid.forEach((line, dr) => {
      line.forEach((value, dc) => {
        const targetRow = next[rowIndex + dr]
        const targetCol = columns[colIndex + dc]
        if (targetRow && targetCol) {
          const match = targetCol.options?.find(
            (option) =>
              option.value.toLocaleLowerCase('ru') === value.trim().toLocaleLowerCase('ru') ||
              option.label.toLocaleLowerCase('ru') === value.trim().toLocaleLowerCase('ru'),
          )
          targetRow[targetCol.id] = match?.value ?? value
        }
      })
    })
    setRows(next)
    onRowsChange?.(next)
  }

  const runDryRun = () => setErrors(validate ? validate(rows) : [])
  const undo = () => {
    setRows(baseline)
    setErrors([])
    setSaveError(undefined)
    onRowsChange?.(baseline)
    onDiscard?.()
  }
  const save = async () => {
    const nextErrors = validate ? validate(rows) : []
    setErrors(nextErrors)
    if (nextErrors.length > 0) return
    setSaving(true)
    setSaveError(undefined)
    try {
      await onCommit?.(rows)
      setBaseline(rows)
      setErrors([])
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Не удалось сохранить изменения')
    } finally {
      setSaving(false)
    }
  }

  const errorAt = (rowIndex: number, colId: string) =>
    errors.find((error) => error.row === rowIndex && error.col === colId)

  return (
    <div className={cn('space-y-3', className)}>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-small">
          <thead className="bg-surface-raised">
            <tr>
              {columns.map((column) => (
                <th className="px-2 py-1 text-left font-medium text-foreground" key={column.id}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr className="border-t border-border" key={rowIndex}>
                {columns.map((column, colIndex) => {
                  const error = errorAt(rowIndex, column.id)
                  return (
                    <td className="p-1" key={column.id}>
                      {column.editor === 'select' ? (
                        <select
                          aria-invalid={error ? true : undefined}
                          aria-label={`${column.header}, строка ${rowIndex + 1}`}
                          className="h-8 min-w-36 rounded-md border border-input bg-surface px-2 text-small text-foreground aria-invalid:border-status-danger"
                          onChange={(event) => setCell(rowIndex, column.id, event.target.value)}
                          onPaste={(event) => handlePaste(event, rowIndex, colIndex)}
                          value={row[column.id] ?? ''}
                        >
                          <option value="">—</option>
                          {(column.options ?? []).map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <Input
                          aria-invalid={error ? true : undefined}
                          aria-label={`${column.header}, строка ${rowIndex + 1}`}
                          className="h-8"
                          onChange={(event) => setCell(rowIndex, column.id, event.target.value)}
                          onPaste={(event) => handlePaste(event, rowIndex, colIndex)}
                          value={row[column.id] ?? ''}
                        />
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={runDryRun} size="sm" variant="outline">
          Проверить (dry-run)
        </Button>
        <Button disabled={!dirty || saving} onClick={undo} size="sm" variant="ghost">
          Отменить правки
        </Button>
        <Button
          disabled={!dirty || errors.length > 0 || saving}
          onClick={() => void save()}
          size="sm"
        >
          {saving ? 'Сохраняем…' : 'Сохранить'}
        </Button>
        <span className="text-caption text-muted-foreground">
          Можно вставить прямоугольный фрагмент из таблицы (TSV).
        </span>
      </div>

      {errors.length > 0 ? (
        <ul className="space-y-1 text-small text-status-danger" role="alert">
          {errors.map((error, index) => (
            <li key={index}>
              Строка {error.row + 1}, «{columns.find((column) => column.id === error.col)?.header}»:{' '}
              {error.message}
            </li>
          ))}
        </ul>
      ) : null}
      {saveError ? (
        <p className="text-small text-status-danger" role="alert">
          {saveError}
        </p>
      ) : null}
    </div>
  )
}

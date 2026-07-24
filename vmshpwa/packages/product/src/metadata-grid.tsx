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
  validate?: (rows: MetadataRow[]) => MetadataError[]
  onCommit?: (rows: MetadataRow[]) => void
  className?: string
}

export function MetadataGrid({
  columns,
  initialRows,
  validate,
  onCommit,
  className,
}: MetadataGridProps) {
  const [rows, setRows] = useState<MetadataRow[]>(initialRows)
  const [baseline, setBaseline] = useState<MetadataRow[]>(initialRows)
  const [errors, setErrors] = useState<MetadataError[]>([])
  const dirty = rows !== baseline

  const setCell = (rowIndex: number, colId: string, value: string) => {
    setErrors([])
    setRows((prev) =>
      prev.map((row, index) => (index === rowIndex ? { ...row, [colId]: value } : row)),
    )
  }

  const handlePaste = (
    event: ClipboardEvent<HTMLInputElement>,
    rowIndex: number,
    colIndex: number,
  ) => {
    const text = event.clipboardData.getData('text')
    if (!text.includes('\t') && !text.includes('\n')) return
    event.preventDefault()
    setErrors([])
    const grid = text
      .replace(/\r/g, '')
      .split('\n')
      .map((line) => line.split('\t'))
    setRows((prev) => {
      const next = prev.map((row) => ({ ...row }))
      grid.forEach((line, dr) => {
        line.forEach((value, dc) => {
          const targetRow = next[rowIndex + dr]
          const targetCol = columns[colIndex + dc]
          if (targetRow && targetCol) targetRow[targetCol.id] = value
        })
      })
      return next
    })
  }

  const runDryRun = () => setErrors(validate ? validate(rows) : [])
  const undo = () => {
    setRows(baseline)
    setErrors([])
  }
  const save = () => {
    onCommit?.(rows)
    setBaseline(rows)
    setErrors([])
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
                      <Input
                        aria-invalid={error ? true : undefined}
                        aria-label={`${column.header}, строка ${rowIndex + 1}`}
                        className="h-8"
                        onChange={(event) => setCell(rowIndex, column.id, event.target.value)}
                        onPaste={(event) => handlePaste(event, rowIndex, colIndex)}
                        value={row[column.id] ?? ''}
                      />
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
        <Button disabled={!dirty} onClick={undo} size="sm" variant="ghost">
          Отменить правки
        </Button>
        <Button disabled={!dirty || errors.length > 0} onClick={save} size="sm">
          Сохранить
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
    </div>
  )
}

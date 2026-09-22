import {
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
  type PointerEvent,
} from 'react'

import { cn } from '@vmsh/ui'

import { cellRange, selectionContains } from './metadata-grid-model'
import type {
  CellAddress,
  GridSelection,
  MetadataColumn,
  MetadataError,
  MetadataRow,
} from './metadata-grid-types'

function rangeLabel(selection: GridSelection | null): string | undefined {
  if (!selection) return undefined
  const range = cellRange(selection)
  return `Выделено строк ${range.firstRow + 1}–${range.lastRow + 1}, столбцов ${range.firstCol + 1}–${range.lastCol + 1}`
}

export function MetadataGridTable({
  columns,
  rows,
  selection,
  widths,
  errors,
  disabled,
  className,
  onSelectionChange,
  onOpenCell,
  onStartTyping,
  onClearSelection,
  onCopy,
  onPaste,
  onResize,
  onGridKeyDown,
}: {
  columns: MetadataColumn[]
  rows: MetadataRow[]
  selection: GridSelection | null
  widths: Record<string, number>
  errors: MetadataError[]
  disabled?: boolean
  className?: string
  onSelectionChange: (selection: GridSelection) => void
  onOpenCell: (address: CellAddress) => void
  onStartTyping: (address: CellAddress, value: string) => void
  onClearSelection: () => void
  onCopy: (event: ClipboardEvent<HTMLDivElement>) => void
  onPaste: (event: ClipboardEvent<HTMLDivElement>) => void
  onResize: (column: MetadataColumn, width: number) => void
  onGridKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void
}) {
  const gridRef = useRef<HTMLDivElement>(null)
  const [dragAnchor, setDragAnchor] = useState<CellAddress | null>(null)

  useEffect(() => {
    const stop = () => setDragAnchor(null)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    return () => {
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
    }
  }, [])

  const move = (from: CellAddress, deltaRow: number, deltaCol: number, extend: boolean) => {
    if (!rows.length || !columns.length) return
    const next = {
      row: Math.max(0, Math.min(rows.length - 1, from.row + deltaRow)),
      col: Math.max(0, Math.min(columns.length - 1, from.col + deltaCol)),
    }
    onSelectionChange({ anchor: extend ? (selection?.anchor ?? from) : next, focus: next })
    queueMicrotask(() => {
      gridRef.current
        ?.querySelector<HTMLElement>(`[data-grid-cell="${next.row}:${next.col}"]`)
        ?.focus({ preventScroll: false })
    })
  }

  const onCellKeyDown = (event: KeyboardEvent<HTMLElement>, address: CellAddress) => {
    if (disabled) return
    const extend = event.shiftKey
    const primary = event.metaKey || event.ctrlKey
    if (primary && event.key.toLocaleLowerCase('ru') === 'a') {
      event.preventDefault()
      onSelectionChange({
        anchor: { row: 0, col: 0 },
        focus: { row: rows.length - 1, col: columns.length - 1 },
      })
      return
    }
    if (primary && event.key.toLocaleLowerCase('ru') === 'z') return
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      move(address, -1, 0, extend)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      move(address, 1, 0, extend)
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault()
      move(address, 0, -1, extend)
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      move(address, 0, 1, extend)
    } else if (event.key === 'Home') {
      event.preventDefault()
      move(address, primary ? -rows.length : 0, primary ? -columns.length : -address.col, extend)
    } else if (event.key === 'End') {
      event.preventDefault()
      move(
        address,
        primary ? rows.length : 0,
        primary ? columns.length : columns.length - 1 - address.col,
        extend,
      )
    } else if (event.key === 'Enter' || event.key === 'F2') {
      event.preventDefault()
      onOpenCell(address)
    } else if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault()
      onClearSelection()
    } else if (
      event.key.length === 1 &&
      !primary &&
      !event.altKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault()
      onStartTyping(address, event.key)
    }
  }

  const resizeStart = (event: PointerEvent<HTMLButtonElement>, column: MetadataColumn) => {
    event.preventDefault()
    event.stopPropagation()
    const startX = event.clientX
    const startWidth = widths[column.id] ?? column.width ?? 180
    const update = (moveEvent: globalThis.PointerEvent) => {
      const min = column.minWidth ?? 80
      const max = column.maxWidth ?? 640
      onResize(column, Math.max(min, Math.min(max, startWidth + moveEvent.clientX - startX)))
    }
    const stop = () => {
      window.removeEventListener('pointermove', update)
      window.removeEventListener('pointerup', stop)
    }
    window.addEventListener('pointermove', update)
    window.addEventListener('pointerup', stop, { once: true })
  }

  return (
    <div
      aria-label="Таблица метаданных задач"
      aria-multiselectable="true"
      aria-rowcount={rows.length}
      aria-colcount={columns.length}
      className={cn('min-h-0 overflow-auto rounded-md border border-border bg-surface', className)}
      onCopy={onCopy}
      onKeyDown={onGridKeyDown}
      onPaste={onPaste}
      ref={gridRef}
      role="grid"
      tabIndex={-1}
    >
      <span className="sr-only" role="status">
        {rangeLabel(selection)}
      </span>
      <table
        className="border-separate border-spacing-0 table-fixed text-small"
        style={{
          width: columns.reduce(
            (total, column) => total + (widths[column.id] ?? column.width ?? 180),
            0,
          ),
        }}
      >
        <colgroup>
          {columns.map((column) => (
            <col key={column.id} style={{ width: widths[column.id] ?? column.width ?? 180 }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column, colIndex) => (
              <th
                className={cn(
                  'sticky top-0 z-20 border-b border-border bg-surface-raised px-2 py-2 text-left font-medium text-foreground',
                  colIndex === 0 && 'left-0 z-30',
                )}
                key={column.id}
                scope="col"
              >
                <span className="block truncate pr-2">{column.header}</span>
                <button
                  aria-label={`Изменить ширину столбца «${column.header}»`}
                  className="absolute top-0 right-0 h-full w-2 cursor-col-resize touch-none outline-none focus-visible:bg-ring/40"
                  onKeyDown={(event) => {
                    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
                    event.preventDefault()
                    const current = widths[column.id] ?? column.width ?? 180
                    const delta = event.key === 'ArrowLeft' ? -16 : 16
                    onResize(
                      column,
                      Math.max(
                        column.minWidth ?? 80,
                        Math.min(column.maxWidth ?? 640, current + delta),
                      ),
                    )
                  }}
                  onPointerDown={(event) => resizeStart(event, column)}
                  type="button"
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} role="row">
              {columns.map((column, colIndex) => {
                const address = { row: rowIndex, col: colIndex }
                const selected = selectionContains(selection, address)
                const active = selection?.focus.row === rowIndex && selection.focus.col === colIndex
                const error = errors.find((item) => item.row === rowIndex && item.col === column.id)
                return (
                  <td
                    aria-label={`${column.header}, строка ${rowIndex + 1}`}
                    aria-describedby={error ? `metadata-error-${rowIndex}-${column.id}` : undefined}
                    aria-invalid={error ? true : undefined}
                    aria-selected={selected}
                    className={cn(
                      'relative h-11 border-r border-b border-border bg-surface px-2 py-1 align-top outline-none',
                      colIndex === 0 && 'sticky left-0 z-10 bg-surface-raised',
                      selected && 'bg-primary/10',
                      active && 'ring-2 ring-inset ring-ring',
                      error && 'bg-destructive/10',
                      disabled && 'cursor-not-allowed opacity-60',
                    )}
                    data-grid-cell={`${rowIndex}:${colIndex}`}
                    key={column.id}
                    onDoubleClick={() => !disabled && onOpenCell(address)}
                    onKeyDown={(event) => onCellKeyDown(event, address)}
                    onPointerDown={(event) => {
                      if (disabled || event.button !== 0) return
                      event.preventDefault()
                      const anchor = event.shiftKey ? (selection?.anchor ?? address) : address
                      setDragAnchor(anchor)
                      onSelectionChange({ anchor, focus: address })
                      event.currentTarget.focus({ preventScroll: true })
                    }}
                    onPointerEnter={() => {
                      if (dragAnchor) onSelectionChange({ anchor: dragAnchor, focus: address })
                    }}
                    role="gridcell"
                    tabIndex={active ? 0 : -1}
                  >
                    <span className="line-clamp-2 block whitespace-pre-wrap break-words text-left">
                      {row[column.id] ?? ''}
                    </span>
                    {error ? (
                      <span className="sr-only" id={`metadata-error-${rowIndex}-${column.id}`}>
                        {error.message}
                      </span>
                    ) : null}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

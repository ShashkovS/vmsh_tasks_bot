import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import {
  Checkbox,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  cn,
} from '@vmsh/ui'

/*
 * Dense staff data table: sticky header, sortable columns, optional row
 * selection, horizontal scroll for wide content. Rows and controls are reachable
 * with the keyboard through the native table + focusable controls.
 */
export interface DenseColumn<T> {
  id: string
  header: string
  cell: (row: T) => ReactNode
  sortValue?: (row: T) => string | number
  align?: 'end'
}

export interface DenseDataTableProps<T> {
  columns: DenseColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string
  selectable?: boolean | undefined
  selected?: ReadonlySet<string> | undefined
  onSelectedChange?: ((next: Set<string>) => void) | undefined
  caption?: string | undefined
  className?: string | undefined
}

export function DenseDataTable<T>({
  columns,
  rows,
  rowKey,
  selectable,
  selected,
  onSelectedChange,
  caption,
  className,
}: DenseDataTableProps<T>) {
  const [sortId, setSortId] = useState<string | null>(null)
  const [dir, setDir] = useState<'asc' | 'desc'>('asc')

  const sortCol = columns.find((column) => column.id === sortId && column.sortValue)
  const sorted = sortCol
    ? [...rows].sort((a, b) => {
        const av = sortCol.sortValue!(a)
        const bv = sortCol.sortValue!(b)
        const cmp =
          typeof av === 'number' && typeof bv === 'number'
            ? av - bv
            : String(av).localeCompare(String(bv), 'ru', { numeric: true })
        return dir === 'asc' ? cmp : -cmp
      })
    : rows

  const toggleSort = (id: string) => {
    if (sortId === id) {
      setDir((value) => (value === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortId(id)
      setDir('asc')
    }
  }

  const keys = rows.map(rowKey)
  const allSelected =
    Boolean(selected) && keys.length > 0 && keys.every((key) => selected!.has(key))
  const someSelected = Boolean(selected) && keys.some((key) => selected!.has(key))

  const toggleAll = () => onSelectedChange?.(allSelected ? new Set() : new Set(keys))
  const toggleRow = (key: string) => {
    if (!onSelectedChange || !selected) return
    const next = new Set(selected)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onSelectedChange(next)
  }

  return (
    <div
      className={cn('max-h-96 overflow-auto rounded-md border border-border', className)}
      data-density="staff"
    >
      <Table>
        {caption ? <TableCaption className="sr-only">{caption}</TableCaption> : null}
        <TableHeader className="sticky top-0 z-10 bg-surface-raised">
          <TableRow>
            {selectable ? (
              <TableHead className="w-8">
                <Checkbox
                  aria-label="Выбрать все строки"
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  onCheckedChange={toggleAll}
                />
              </TableHead>
            ) : null}
            {columns.map((column) => (
              <TableHead
                aria-sort={
                  sortId === column.id ? (dir === 'asc' ? 'ascending' : 'descending') : undefined
                }
                className={column.align === 'end' ? 'text-right' : undefined}
                key={column.id}
              >
                {column.sortValue ? (
                  <button
                    className="inline-flex items-center gap-1 font-medium text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                    onClick={() => toggleSort(column.id)}
                    type="button"
                  >
                    {column.header}
                    {sortId === column.id ? (
                      dir === 'asc' ? (
                        <ArrowUp aria-hidden="true" className="size-3.5" />
                      ) : (
                        <ArrowDown aria-hidden="true" className="size-3.5" />
                      )
                    ) : (
                      <ArrowUpDown aria-hidden="true" className="size-3.5 text-muted-foreground" />
                    )}
                  </button>
                ) : (
                  column.header
                )}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row) => {
            const key = rowKey(row)
            const isSelected = Boolean(selected?.has(key))
            return (
              <TableRow
                className={isSelected ? 'bg-primary/5' : undefined}
                data-selected={isSelected || undefined}
                key={key}
              >
                {selectable ? (
                  <TableCell>
                    <Checkbox
                      aria-label="Выбрать строку"
                      checked={isSelected}
                      onCheckedChange={() => toggleRow(key)}
                    />
                  </TableCell>
                ) : null}
                {columns.map((column) => (
                  <TableCell
                    className={column.align === 'end' ? 'text-right' : undefined}
                    key={column.id}
                  >
                    {column.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

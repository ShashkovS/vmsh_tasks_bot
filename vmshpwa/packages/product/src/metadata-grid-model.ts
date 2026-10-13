import type {
  CellAddress,
  CellChange,
  GridEdit,
  GridModel,
  GridSelection,
  MetadataColumn,
  MetadataRow,
} from './metadata-grid-types'

const MAX_HISTORY = 100

export function cloneRows(rows: MetadataRow[]): MetadataRow[] {
  return rows.map((row) => ({ ...row }))
}

export function rowsEqual(left: MetadataRow[], right: MetadataRow[]): boolean {
  return (
    left.length === right.length &&
    left.every((row, rowIndex) => {
      const other = right[rowIndex]
      const keys = new Set([...Object.keys(row), ...Object.keys(other ?? {})])
      return [...keys].every((key) => row[key] === other?.[key])
    })
  )
}

export function cellRange(selection: GridSelection): {
  firstRow: number
  lastRow: number
  firstCol: number
  lastCol: number
} {
  return {
    firstRow: Math.min(selection.anchor.row, selection.focus.row),
    lastRow: Math.max(selection.anchor.row, selection.focus.row),
    firstCol: Math.min(selection.anchor.col, selection.focus.col),
    lastCol: Math.max(selection.anchor.col, selection.focus.col),
  }
}

export function selectionContains(selection: GridSelection | null, address: CellAddress): boolean {
  if (!selection) return false
  const range = cellRange(selection)
  return (
    address.row >= range.firstRow &&
    address.row <= range.lastRow &&
    address.col >= range.firstCol &&
    address.col <= range.lastCol
  )
}

export function clampAddress(
  address: CellAddress,
  rowCount: number,
  columnCount: number,
): CellAddress | null {
  if (!rowCount || !columnCount) return null
  return {
    row: Math.max(0, Math.min(rowCount - 1, address.row)),
    col: Math.max(0, Math.min(columnCount - 1, address.col)),
  }
}

export function createCellEdit(
  rows: MetadataRow[],
  columns: MetadataColumn[],
  row: number,
  col: number,
  after: string,
  selectionBefore: GridSelection | null,
  selectionAfter: GridSelection | null,
): GridEdit | null {
  const column = columns[col]
  const target = rows[row]
  if (!column || !target) return null
  const before = target[column.id] ?? ''
  if (before === after) return null
  return {
    changes: [{ row, columnId: column.id, before, after }],
    selectionBefore,
    selectionAfter,
  }
}

export function applyEdit(
  rows: MetadataRow[],
  edit: GridEdit,
  direction: 'redo' | 'undo',
): MetadataRow[] {
  const updates = new Map<number, Record<string, string>>()
  for (const change of edit.changes) {
    const target = rows[change.row]
    if (!target) continue
    const values = updates.get(change.row) ?? { ...target }
    values[change.columnId] = direction === 'redo' ? change.after : change.before
    updates.set(change.row, values)
  }
  if (!updates.size) return rows
  return rows.map((row, index) => updates.get(index) ?? row)
}

export function applyNewEdit(model: GridModel, edit: GridEdit): GridModel {
  if (!edit.changes.length) return model
  return {
    ...model,
    rows: applyEdit(model.rows, edit, 'redo'),
    selection: edit.selectionAfter,
    undo: [...model.undo, edit].slice(-MAX_HISTORY),
    redo: [],
  }
}

export function undoModel(model: GridModel): GridModel {
  const edit = model.undo.at(-1)
  if (!edit) return model
  return {
    ...model,
    rows: applyEdit(model.rows, edit, 'undo'),
    selection: edit.selectionBefore,
    undo: model.undo.slice(0, -1),
    redo: [edit, ...model.redo],
  }
}

export function redoModel(model: GridModel): GridModel {
  const edit = model.redo[0]
  if (!edit) return model
  return {
    ...model,
    rows: applyEdit(model.rows, edit, 'redo'),
    selection: edit.selectionAfter,
    undo: [...model.undo, edit].slice(-MAX_HISTORY),
    redo: model.redo.slice(1),
  }
}

export function resetModel(model: GridModel): GridModel {
  return { ...model, rows: cloneRows(model.baseline), undo: [], redo: [] }
}

export function commitModel(model: GridModel): GridModel {
  return { ...model, baseline: cloneRows(model.rows), undo: [], redo: [] }
}

export function pasteEdit(
  rows: MetadataRow[],
  columns: MetadataColumn[],
  start: CellAddress,
  values: string[][],
  selectionBefore: GridSelection | null,
): GridEdit | null {
  const changes: CellChange[] = []
  values.forEach((line, rowOffset) => {
    line.forEach((value, columnOffset) => {
      const row = start.row + rowOffset
      const column = columns[start.col + columnOffset]
      const target = rows[row]
      if (!column || !target) return
      const before = target[column.id] ?? ''
      if (before !== value) changes.push({ row, columnId: column.id, before, after: value })
    })
  })
  if (!changes.length) return null
  return {
    changes,
    selectionBefore,
    selectionAfter: {
      anchor: start,
      focus: { row: start.row + values.length - 1, col: start.col + values[0]!.length - 1 },
    },
  }
}

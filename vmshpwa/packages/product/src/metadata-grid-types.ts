/** Public contract for the Staff metadata spreadsheet (METADATA-01..03). */
export interface MetadataColumn {
  id: string
  header: string
  editor?: 'text' | 'select' | 'textarea'
  options?: { value: string; label: string; clipboardLabel?: string }[]
  /** Initial width of the visible column, in pixels. */
  width?: number
  minWidth?: number
  maxWidth?: number
  /** Stable header used when the whole grid is exchanged as TSV. */
  clipboardHeader?: string
  /** Kept for existing consumers during the transition to width-based columns. */
  editorClassName?: string
}

export interface MetadataError {
  row: number
  col: string
  message: string
}

export type MetadataRow = Record<string, string>

export interface MetadataGridProps {
  allowPristineCommit?: boolean
  columns: MetadataColumn[]
  initialRows: MetadataRow[]
  initialDraftRows?: MetadataRow[]
  validate?: (rows: MetadataRow[]) => MetadataError[]
  onRowsChange?: (rows: MetadataRow[]) => void
  onDiscard?: () => void
  onCommit?: (rows: MetadataRow[]) => void | Promise<void>
  onDirtyChange?: (dirty: boolean) => void
  className?: string
  commitLabel?: string
  title?: string
  disabled?: boolean
}

export interface CellAddress {
  row: number
  col: number
}

export interface GridSelection {
  anchor: CellAddress
  focus: CellAddress
}

export interface CellChange {
  row: number
  columnId: string
  before: string
  after: string
}

export interface GridEdit {
  changes: CellChange[]
  selectionBefore: GridSelection | null
  selectionAfter: GridSelection | null
}

export interface GridModel {
  baseline: MetadataRow[]
  rows: MetadataRow[]
  selection: GridSelection | null
  undo: GridEdit[]
  redo: GridEdit[]
}

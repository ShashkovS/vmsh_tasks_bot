import type { MetadataColumn, MetadataRow } from './metadata-grid-types'

export type ClipboardParseResult =
  { ok: true; rows: string[][] } | { ok: false; reason: 'quotes' | 'shape' }

/** Parses Excel/Google Sheets text/plain TSV, including quoted multiline values. */
export function parseMetadataTsv(text: string): ClipboardParseResult {
  const rows: string[][] = []
  let row: string[] = []
  let value = ''
  let quoted = false
  let atFieldStart = true
  let endedWithRowBreak = false

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]!
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          value += '"'
          index += 1
        } else {
          quoted = false
          atFieldStart = false
        }
      } else {
        value += char === '\r' && text[index + 1] === '\n' ? '\n' : char
        if (char === '\r' && text[index + 1] === '\n') index += 1
      }
      continue
    }
    if (char === '"' && atFieldStart) {
      quoted = true
      endedWithRowBreak = false
    } else if (char === '\t') {
      row.push(value)
      value = ''
      atFieldStart = true
      endedWithRowBreak = false
    } else if (char === '\n' || char === '\r') {
      row.push(value)
      rows.push(row)
      row = []
      value = ''
      atFieldStart = true
      endedWithRowBreak = true
      if (char === '\r' && text[index + 1] === '\n') index += 1
    } else {
      value += char
      atFieldStart = false
      endedWithRowBreak = false
    }
  }
  if (quoted) return { ok: false, reason: 'quotes' }
  if (!endedWithRowBreak || row.length || value) {
    row.push(value)
    rows.push(row)
  }
  if (!rows.length || rows.some((row) => row.length !== rows[0]!.length)) {
    return { ok: false, reason: 'shape' }
  }
  return { ok: true, rows }
}

export function serializeMetadataTsv(rows: string[][]): string {
  return rows
    .map((row) =>
      row
        .map((value) => (/["\t\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value))
        .join('\t'),
    )
    .join('\n')
}

export function clipboardValue(value: string, column: MetadataColumn): string {
  const option = column.options?.find((candidate) => candidate.value === value)
  return option?.clipboardLabel ?? option?.label ?? value
}

/** Human-readable table value. Stored rows retain the stable option code. */
export function displayMetadataValue(value: string, column: MetadataColumn): string {
  return column.options?.find((candidate) => candidate.value === value)?.label ?? value
}

export function normalizeClipboardValue(value: string, column: MetadataColumn): string {
  if (!column.options) return value
  const normalized = value.trim().toLocaleLowerCase('ru')
  if (!normalized || normalized === '—') return ''
  return (
    column.options.find((candidate) =>
      [candidate.value, candidate.label, candidate.clipboardLabel]
        .filter((entry): entry is string => entry !== undefined)
        .some((entry) => entry.toLocaleLowerCase('ru') === normalized),
    )?.value ?? value
  )
}

export function metadataHeaders(columns: MetadataColumn[]): string[] {
  return columns.map((column) => column.clipboardHeader ?? column.header)
}

export function hasMetadataHeaders(values: string[], columns: MetadataColumn[]): boolean {
  if (values.length !== columns.length) return false
  return values.every((value, index) => {
    const column = columns[index]!
    return value === (column.clipboardHeader ?? column.header) || value === column.header
  })
}

export function matrixFromRows(
  rows: MetadataRow[],
  columns: MetadataColumn[],
  includeHeaders = false,
): string[][] {
  const values = rows.map((row) =>
    columns.map((column) => clipboardValue(row[column.id] ?? '', column)),
  )
  return includeHeaders ? [metadataHeaders(columns), ...values] : values
}

import { describe, expect, it } from 'vitest'

import {
  hasMetadataHeaders,
  normalizeClipboardValue,
  parseMetadataTsv,
  serializeMetadataTsv,
} from './metadata-grid-clipboard'
import type { MetadataColumn } from './metadata-grid-types'

const columns: MetadataColumn[] = [
  { id: 'number', header: 'Номер' },
  {
    id: 'kind',
    header: 'Тип задачи',
    options: [{ value: '1', label: 'Тестовая' }],
  },
]

describe('metadata TSV exchange', () => {
  it('round-trips quotes, tabs, newlines and empty values', () => {
    const original = [
      ['0018', ''],
      ['«Куб»\nс\tтабуляцией', '"цитата"'],
    ]
    expect(parseMetadataTsv(serializeMetadataTsv(original))).toEqual({ ok: true, rows: original })
  })

  it('does not create a phantom cell for a trailing row break', () => {
    expect(parseMetadataTsv('1\t2\n3\t4\n')).toEqual({
      ok: true,
      rows: [
        ['1', '2'],
        ['3', '4'],
      ],
    })
  })

  it('recognizes visible labels and complete headers', () => {
    expect(normalizeClipboardValue('тестовая', columns[1]!)).toBe('1')
    expect(hasMetadataHeaders(['Номер', 'Тип задачи'], columns)).toBe(true)
  })

  it('rejects malformed quoted input without producing a partial grid', () => {
    expect(parseMetadataTsv('"незакрытая')).toEqual({ ok: false, reason: 'quotes' })
    expect(parseMetadataTsv('1\t2\n3')).toEqual({ ok: false, reason: 'shape' })
  })
})

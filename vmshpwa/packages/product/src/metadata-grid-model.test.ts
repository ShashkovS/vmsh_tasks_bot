import { describe, expect, it } from 'vitest'

import {
  applyNewEdit,
  createCellEdit,
  pasteEdit,
  redoModel,
  rowsEqual,
  undoModel,
} from './metadata-grid-model'
import type { GridModel, MetadataColumn, MetadataRow } from './metadata-grid-types'

const columns: MetadataColumn[] = [
  { id: 'title', header: 'Название' },
  { id: 'kind', header: 'Тип' },
]
const rows: MetadataRow[] = [
  { problemId: '10', title: 'Первая', kind: '1' },
  { problemId: '20', title: 'Вторая', kind: '2' },
]
const model: GridModel = {
  baseline: rows,
  rows,
  selection: { anchor: { row: 0, col: 0 }, focus: { row: 0, col: 0 } },
  undo: [],
  redo: [],
}

describe('metadata grid model', () => {
  it('undoes and redoes a paste without changing hidden identity', () => {
    const edit = pasteEdit(
      rows,
      columns,
      { row: 0, col: 0 },
      [
        ['Один', '2'],
        ['Два', '1'],
      ],
      model.selection,
    )
    expect(edit).not.toBeNull()
    const changed = applyNewEdit(model, edit!)
    expect(changed.rows).toEqual([
      { problemId: '10', title: 'Один', kind: '2' },
      { problemId: '20', title: 'Два', kind: '1' },
    ])
    expect(undoModel(changed).rows).toEqual(rows)
    expect(redoModel(undoModel(changed)).rows).toEqual(changed.rows)
  })

  it('does not create history for an unchanged cell', () => {
    expect(
      createCellEdit(rows, columns, 0, 0, 'Первая', model.selection, model.selection),
    ).toBeNull()
    expect(
      rowsEqual(
        rows,
        rows.map((row) => ({ ...row })),
      ),
    ).toBe(true)
  })
})

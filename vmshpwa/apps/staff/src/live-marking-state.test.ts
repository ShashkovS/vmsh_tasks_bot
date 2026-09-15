import { describe, expect, it } from 'vitest'
import type { LiveCells } from '@vmsh/contracts'
import { emptyLiveCell, mergeLiveCells } from './live-marking-state'

const snapshot = (version: number, symbol = '+'): LiveCells => ({
  schemaVersion: 1,
  requestId: 'r',
  cursor: 1,
  scope: 'a'.repeat(64),
  reset: false,
  cells: [{ ...emptyLiveCell('u-1', 'p-1'), version, symbol }],
})
describe('live-marking.md: authority response / receipt races', () => {
  it('keeps a colleague update when an old idempotency receipt arrives', () => {
    expect(mergeLiveCells(snapshot(1, '+'), snapshot(2, '−')).cells[0]?.symbol).toBe('−')
  })
  it('keeps a receipt that arrives after an empty initial snapshot began', () => {
    expect(
      mergeLiveCells({ ...snapshot(0), cells: [], reset: true }, snapshot(1)).cells,
    ).toHaveLength(1)
  })
  it('applies an undo tombstone and ignores a delayed earlier plus', () => {
    const current = mergeLiveCells(snapshot(3, ''), snapshot(2))
    expect(mergeLiveCells(snapshot(2), current).cells[0]?.symbol).toBe('')
  })
  it('drops cells when transfer or permission changes the membership scope', () => {
    expect(
      mergeLiveCells({ ...snapshot(0), cells: [], scope: 'b'.repeat(64), reset: true }, snapshot(1))
        .cells,
    ).toEqual([])
  })
})

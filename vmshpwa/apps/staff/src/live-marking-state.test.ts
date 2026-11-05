import { describe, expect, it } from 'vitest'
import type { LiveCells } from '@vmsh/contracts'
import { emptyLiveCell, mergeLiveCells, zoomLessonSelection } from './live-marking-state'

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

describe('live-marking.md: Zoom worksheet level is independent of enrollment', () => {
  const lessons = [
    { lessonId: 'n2', number: 2, groupId: 'n', groupName: 'Начинающие' },
    { lessonId: 'p2', number: 2, groupId: 'p', groupName: 'Продолжающие' },
    { lessonId: 'n1', number: 1, groupId: 'n', groupName: 'Начинающие' },
    { lessonId: 'e1', number: 1, groupId: 'e', groupName: 'Эксперты' },
  ]
  it('restores another level from URL / visits and limits the lesson picker to it', () => {
    const selection = zoomLessonSelection(lessons, 'n', 'p2')
    expect(selection.lesson?.lessonId).toBe('p2')
    expect(selection.lessons.map((item) => item.lessonId)).toEqual(['p2'])
    expect(selection.groups.map((item) => item.target?.lessonId)).toEqual(['n2', 'p2', undefined])
  })
  it('defaults to latest own level for a new student', () => {
    expect(zoomLessonSelection(lessons, 'n').lesson?.lessonId).toBe('n2')
    expect(zoomLessonSelection(lessons, 'e').lesson?.lessonId).toBe('e1')
  })
  it('keeps empty own level and offers latest worksheets in other levels', () => {
    const selection = zoomLessonSelection(lessons, 'unpublished')
    expect(selection.lesson).toBeUndefined()
    expect(selection.groups.map((item) => item.target?.lessonId)).toEqual(['n2', 'p2', 'e1'])
  })
  it('never substitutes another lesson number when switching levels', () => {
    const selection = zoomLessonSelection(lessons, 'n', 'n1')
    expect(selection.groups.find((item) => item.id === 'p')?.target).toBeUndefined()
    expect(selection.groups.find((item) => item.id === 'e')?.target?.lessonId).toBe('e1')
    expect(zoomLessonSelection([], 'n').groups).toEqual([])
  })
})

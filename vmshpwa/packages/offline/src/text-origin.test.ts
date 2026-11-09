import { describe, expect, it } from 'vitest'
import { packTextOrigin, TextOriginHistory } from './text-origin'
import type { TextOrigin } from '@vmsh/contracts'

function count(origin: TextOrigin | null) {
  return origin
    ? [...atob(origin.bits)].reduce(
        (sum, byte) => sum + byte.charCodeAt(0).toString(2).replaceAll('0', '').length,
        0,
      )
    : null
}

describe('remaining pasted text (docs/paste-evidence.md)', () => {
  it('tracks mixed input, multiple pastes and deletion of only pasted characters', () => {
    const history = new TextOriginHistory()
    let origin = history.edit('', 'abcd', packTextOrigin(new Uint8Array()), {
      start: 0,
      end: 0,
      pasted: true,
    })
    expect(count(origin)).toBe(4)
    origin = history.edit('abcd', 'abcdEF', origin, { start: 4, end: 4 })
    expect(count(origin)).toBe(4)
    origin = history.edit('abcdEF', 'abcdEFgh', origin, {
      start: 6,
      end: 6,
      inputType: 'insertFromPaste',
    })
    expect(count(origin)).toBe(6)
    origin = history.edit('abcdEFgh', 'aEFgh', origin, { start: 1, end: 4 })
    expect(count(origin)).toBe(3)
    origin = history.edit('aEFgh', 'EF', origin)
    expect(count(origin)).toBe(0)
  })

  it('replaces selected repeated text even when the visible text is identical', () => {
    const history = new TextOriginHistory()
    const typed = packTextOrigin(new Uint8Array(4))
    const origin = history.edit('aaaa', 'aaaa', typed, { start: 1, end: 3, pasted: true })
    expect(count(origin)).toBe(2)
    expect(count(history.edit('aaaa', 'aaaa', origin, { start: 1, end: 3 }))).toBe(0)
  })

  it('preserves undo/redo provenance and UTF-16 surrogate pairs', () => {
    const history = new TextOriginHistory()
    const empty = packTextOrigin(new Uint8Array())
    const pasted = history.edit('', '😀', empty, { start: 0, end: 0, pasted: true })
    expect(pasted?.utf16Length).toBe(2)
    expect(count(pasted)).toBe(2)
    const undone = history.edit('😀', '', pasted, { start: 2, end: 2, inputType: 'historyUndo' })
    expect(count(undone)).toBe(0)
    expect(
      count(history.edit('', '😀', undone, { start: 0, end: 0, inputType: 'historyRedo' })),
    ).toBe(2)
  })

  it('keeps old drafts unknown until cleared and degrades unavailable undo safely', () => {
    const history = new TextOriginHistory()
    expect(history.edit('old', 'old!', null)).toBeNull()
    const empty = history.edit('old!', '', null)
    expect(count(empty)).toBe(0)
    expect(count(history.edit('', 'typed', empty))).toBe(0)
    expect(
      history.edit('typed', 'unavailable', packTextOrigin(new Uint8Array(5)), {
        start: 0,
        end: 0,
        inputType: 'historyUndo',
      }),
    ).toBeNull()
  })
})

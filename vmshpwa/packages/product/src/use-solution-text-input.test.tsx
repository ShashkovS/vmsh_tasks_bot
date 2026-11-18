import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useSolutionTextInput } from './use-solution-text-input'

afterEach(cleanup)

it('only records paste on an actual change, ignores a cancelled paste, and handles native undo', () => {
  const changed = vi.fn()
  function Field() {
    const [text, setText] = useState('')
    const input = useSolutionTextInput((value, edit) => {
      setText(value)
      changed(value, edit)
    })
    return <textarea aria-label="solution" value={text} {...input} />
  }
  render(<Field />)
  const field = screen.getByRole('textbox')
  fireEvent.paste(field, { clipboardData: { getData: () => 'abc' } })
  expect(changed).not.toHaveBeenCalled()
  fireEvent.input(field, { target: { value: 'abc' }, inputType: 'insertFromPaste' })
  expect(changed).toHaveBeenLastCalledWith('abc', expect.objectContaining({ pasted: true }))
  fireEvent.paste(field, { clipboardData: { getData: () => 'cancelled' } })
  fireEvent.keyDown(field, { key: 'x' })
  fireEvent.input(field, { target: { value: 'abcx' }, inputType: 'insertText' })
  expect(changed).toHaveBeenLastCalledWith('abcx', expect.objectContaining({ pasted: false }))
  fireEvent.input(field, { target: { value: 'abc' }, inputType: 'historyUndo' })
  expect(changed).toHaveBeenLastCalledWith(
    'abc',
    expect.objectContaining({ inputType: 'historyUndo' }),
  )
})

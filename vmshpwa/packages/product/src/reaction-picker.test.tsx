import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { reactionsForScope } from './reaction'
import { ReactionPicker } from './reaction-picker'

afterEach(() => cleanup())

describe('ReactionPicker keyboard shortcuts', () => {
  it('uses the physical digit code when Alt changes the printable key on macOS', () => {
    const onSelect = vi.fn()
    render(
      <ReactionPicker
        compact
        hotkeys
        onSelect={onSelect}
        options={reactionsForScope('teacher-written')}
        value={null}
      />,
    )

    fireEvent.keyDown(window, { altKey: true, code: 'Digit1', key: '¡', metaKey: true })

    expect(onSelect).toHaveBeenCalledWith(100)
  })
})

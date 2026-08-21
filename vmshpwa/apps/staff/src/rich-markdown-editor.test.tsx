import { act, cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RichMarkdownEditor } from './rich-markdown-editor'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('RichMarkdownEditor', () => {
  it('treats an empty publication as a neutral draft', () => {
    const onDocumentChange = vi.fn()

    render(<RichMarkdownEditor onChange={vi.fn()} onDocumentChange={onDocumentChange} value="" />)

    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('Предпросмотр появится после ввода текста.')).toBeTruthy()
    expect(onDocumentChange).toHaveBeenCalledWith(null)
  })

  it('keeps the last valid preview while an inline construct is being completed', () => {
    vi.useFakeTimers()
    const onDocumentChange = vi.fn()
    const rendered = render(
      <RichMarkdownEditor
        onChange={vi.fn()}
        onDocumentChange={onDocumentChange}
        value="Исходный текст"
      />,
    )
    const preview = screen.getByLabelText('Предпросмотр Markdown')
    expect(within(preview).getByText('Исходный текст')).toBeTruthy()

    rendered.rerender(
      <RichMarkdownEditor onChange={vi.fn()} onDocumentChange={onDocumentChange} value="**" />,
    )

    expect(screen.getByRole('alert').textContent).toContain('Исправьте ошибку в markdown.')
    expect(within(preview).getByText('Исходный текст')).toBeTruthy()
    expect(onDocumentChange).toHaveBeenLastCalledWith(null)

    act(() => {
      vi.advanceTimersByTime(2_000)
    })

    expect(within(preview).queryByText('Исходный текст')).toBeNull()
    expect(within(preview).getByText('Исправьте ошибку в markdown.')).toBeTruthy()
  })
})

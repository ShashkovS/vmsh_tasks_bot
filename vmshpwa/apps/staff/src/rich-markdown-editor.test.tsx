import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'

import { RichMarkdownEditor } from './rich-markdown-editor'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('RichMarkdownEditor', () => {
  it('inserts a file into the current text after editing during upload', async () => {
    let resolve!: (value: {
      url: string
      filename: string
      mimeType: string
      byteSize: number
    }) => void
    const onFileUpload = vi.fn().mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const onChange = vi.fn()
    function ControlledEditor() {
      const [value, setValue] = useState('Начальный текст')
      return (
        <RichMarkdownEditor
          value={value}
          onFileUpload={onFileUpload}
          onChange={(next) => {
            onChange(next)
            setValue(next)
          }}
        />
      )
    }
    render(<ControlledEditor />)
    fireEvent.change(screen.getByLabelText('Файл для прикрепления'), {
      target: { files: [new File(['pdf'], 'Условия.pdf')] },
    })
    // A controlled update while the server is still receiving the attachment.
    // CodeMirror owns input; exercise its normal editing transaction.
    const { EditorView } = await import('@codemirror/view')
    const view = EditorView.findFromDOM(screen.getByLabelText('Markdown публикации'))
    expect(view).toBeTruthy()
    act(() =>
      view!.dispatch({
        changes: { from: 0, to: view!.state.doc.length, insert: 'Текст после правки' },
        selection: { anchor: 5 },
      }),
    )
    resolve({
      url: `/pwa-rich-files/${'a'.repeat(64)}/file.pdf`,
      filename: 'Условия.pdf',
      mimeType: 'application/pdf',
      byteSize: 3,
    })
    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith(expect.stringContaining('после правки')),
    )
    await waitFor(() =>
      expect(screen.getByLabelText('Предпросмотр Markdown').textContent).toContain('Условия.pdf'),
    )
    expect(onChange.mock.calls.at(-1)?.[0]).toMatch(/^Текст\n\n\[Условия.pdf\]/u)
  })
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

  it('uploads an image and inserts its server-owned Markdown URL at the cursor', async () => {
    const onChange = vi.fn()
    const onImageUpload = vi.fn().mockResolvedValue({
      url: 'https://cdn.example.test/rich-media/sha256/aa/picture.webp',
    })
    const { container } = render(
      <RichMarkdownEditor onChange={onChange} onImageUpload={onImageUpload} value="Текст" />,
    )

    const input = container.querySelector('input[type="file"]')
    expect(input).toBeTruthy()
    fireEvent.change(input!, {
      target: {
        files: [new File(['picture'], 'квадрат.png', { type: 'image/png' })],
      },
    })

    await waitFor(() =>
      expect(onChange).toHaveBeenLastCalledWith(
        expect.stringContaining(
          '![квадрат](https://cdn.example.test/rich-media/sha256/aa/picture.webp)',
        ),
      ),
    )
  })
})

it('renders English editor controls while preserving authored Markdown', async () => {
  const { i18n } = await import('@lingui/core')
  i18n.activate('en')
  const authored = 'Авторский текст $x^2$'
  render(<RichMarkdownEditor onChange={vi.fn()} value={authored} />)
  expect(screen.getByLabelText('Publication Markdown').textContent).toBe(authored)
  expect(screen.getByLabelText('Markdown preview').textContent).toContain('Авторский текст')
})

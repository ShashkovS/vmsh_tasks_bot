import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { parseRichMarkdown } from '@vmsh/product'
import { afterEach, expect, it, vi } from 'vitest'
import { StaffFileUpload } from './staff-file-upload'
import { fileAttachmentMarkdown } from './file-attachment-markdown'

afterEach(cleanup)
const attachment = {
  url: `/pwa-rich-files/${'a'.repeat(64)}/file.pdf`,
  filename: 'Условия [1] *x* $1$ <tag> (a).pdf',
  mimeType: 'application/pdf',
  byteSize: 10,
}

it('escapes all filename markup while keeping the link label editable', () => {
  const document = parseRichMarkdown(fileAttachmentMarkdown(attachment))
  expect(document.blocks[0]).toEqual({
    type: 'paragraph',
    children: [
      {
        type: 'link',
        href: attachment.url,
        children: [{ type: 'text', text: attachment.filename }],
      },
    ],
  })
})

it('shows upload feedback, uses the latest insertion callback and permits another file', async () => {
  let resolve!: (value: typeof attachment) => void
  const onUpload = vi.fn().mockReturnValue(
    new Promise<typeof attachment>((done) => {
      resolve = done
    }),
  )
  const oldInsert = vi.fn()
  const currentInsert = vi.fn()
  const rendered = render(<StaffFileUpload onInsert={oldInsert} onUpload={onUpload} />)
  fireEvent.change(screen.getByLabelText('Файл для прикрепления'), {
    target: { files: [new File(['pdf'], 'a.pdf')] },
  })
  expect(screen.getByRole('button', { name: 'Загружаем файл…' })).toHaveProperty('disabled', true)
  expect(screen.getByRole('status')).toBeTruthy()
  rendered.rerender(<StaffFileUpload onInsert={currentInsert} onUpload={onUpload} />)
  resolve(attachment)
  await waitFor(() => expect(currentInsert).toHaveBeenCalledOnce())
  expect(oldInsert).not.toHaveBeenCalled()
  onUpload.mockResolvedValue(attachment)
  fireEvent.change(screen.getByLabelText('Файл для прикрепления'), {
    target: { files: [new File(['pdf'], 'a.pdf')] },
  })
  await waitFor(() => expect(currentInsert).toHaveBeenCalledTimes(2))
})

it.each([new File([], 'empty.pdf'), new File(['binary'], 'bad.exe')])(
  'rejects invalid files before upload',
  (file) => {
    const onUpload = vi.fn()
    render(<StaffFileUpload onInsert={vi.fn()} onUpload={onUpload} />)
    fireEvent.change(screen.getByLabelText('Файл для прикрепления'), { target: { files: [file] } })
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(onUpload).not.toHaveBeenCalled()
  },
)

it('shows a server error without inserting a link', async () => {
  const onInsert = vi.fn()
  render(
    <StaffFileUpload
      onInsert={onInsert}
      onUpload={vi.fn().mockRejectedValue(new Error('Storage unavailable'))}
    />,
  )
  fireEvent.change(screen.getByLabelText('Файл для прикрепления'), {
    target: { files: [new File(['pdf'], 'a.pdf')] },
  })
  await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Storage unavailable'))
  expect(onInsert).not.toHaveBeenCalled()
})

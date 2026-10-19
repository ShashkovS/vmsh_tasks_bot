import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import type { LessonBlockClient } from '@vmsh/app-shell'
import type { StaffRichFile } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { afterEach, expect, it, vi } from 'vitest'
import { StaffLessonBlockEditor } from './staff-lesson-block-editor'

afterEach(cleanup)

it.each(['before', 'after'] as const)(
  'retains edits made while uploading a %s block attachment',
  async (position) => {
    let resolve!: (file: StaffRichFile) => void
    const client = {
      get: () => Promise.reject(new Error('Unused')),
      save: vi.fn().mockResolvedValue(undefined),
      publish: vi.fn().mockResolvedValue(undefined),
      hide: vi.fn().mockResolvedValue(undefined),
      cancel: vi.fn().mockResolvedValue(undefined),
      uploadImage: () => Promise.reject(new Error('Unused')),
      uploadFile: vi.fn().mockReturnValue(
        new Promise<StaffRichFile>((done) => {
          resolve = done
        }),
      ),
    } satisfies LessonBlockClient
    const title = position === 'before' ? 'Блок перед задачами' : 'Блок после задач'
    render(
      <StaffLessonBlockEditor
        block={null}
        businessTimezone="Europe/Moscow"
        client={client}
        groupLessonId="gl-1"
        position={position}
        refetch={vi.fn()}
        title={title}
      />,
    )
    fireEvent.click(screen.getByText(title))
    fireEvent.change(screen.getByLabelText('Файл для прикрепления'), {
      target: { files: [new File(['pdf'], 'Условия.pdf')] },
    })
    const input = screen.getByLabelText<HTMLTextAreaElement>(`${title}: Markdown`)
    fireEvent.change(input, { target: { value: 'Правка во время загрузки' } })
    input.setSelectionRange(6, 6)
    resolve({
      url: `/pwa-rich-files/${'a'.repeat(64)}/document.pdf`,
      filename: 'Условия.pdf',
      mimeType: 'application/pdf',
      byteSize: 3,
    })
    await waitFor(() => expect(input.value).toContain('[Условия.pdf]'))
    expect(input.value).toMatch(/^Правка\n\n\[Условия.pdf\]/u)
    expect(input.value).toContain('во время загрузки')
    expect(client.save).not.toHaveBeenCalled()
    expect(client.publish).not.toHaveBeenCalled()
    const savedMarkdown = input.value
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }))
    await waitFor(() =>
      expect(client.save).toHaveBeenCalledWith(
        'gl-1',
        position,
        '"none"',
        expect.objectContaining({ markdown: savedMarkdown }),
      ),
    )
  },
)

import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, waitFor, within } from 'storybook/test'

import { StaffFileUpload } from './staff-file-upload'

/** Upload feedback/a11y states required by docs/rich-file-attachments.md. */
const meta = {
  title: 'Staff/File attachment',
  component: StaffFileUpload,
  globals: { density: 'staff' },
  args: {
    onInsert: fn(),
    onUpload: fn(() =>
      Promise.resolve({
        url: `/pwa-rich-files/${'a'.repeat(64)}/document.pdf`,
        filename: 'Материалы [1].pdf',
        mimeType: 'application/pdf',
        byteSize: 10,
      }),
    ),
  },
  decorators: [
    (Story) => (
      <div className="max-w-xl bg-surface p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof StaffFileUpload>
export default meta
type Story = StoryObj<typeof meta>

export const Ready: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await userEvent.tab()
    await expect(canvas.getByRole('button', { name: 'Прикрепить файл' })).toHaveFocus()
    await userEvent.upload(
      canvas.getByLabelText('Файл для прикрепления'),
      new File(['pdf'], 'Материалы [1].pdf', { type: 'application/pdf' }),
    )
    await waitFor(() =>
      expect(args.onInsert).toHaveBeenCalledWith(expect.stringContaining('Материалы \\[1\\].pdf')),
    )
    await expect(canvas.getByRole('button', { name: 'Прикрепить файл' })).toBeEnabled()
  },
}
export const Uploading: Story = {
  args: {
    onUpload: fn(
      () =>
        new Promise<{ url: string; filename: string; mimeType: string; byteSize: number }>(
          () => {},
        ),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.upload(
      canvas.getByLabelText('Файл для прикрепления'),
      new File(['pdf'], 'document.pdf', { type: 'application/pdf' }),
    )
    await expect(canvas.getByRole('button', { name: 'Загружаем файл…' })).toBeDisabled()
    await expect(canvas.getByRole('status')).toBeVisible()
  },
}
export const Failed: Story = {
  args: { onUpload: fn(() => Promise.reject(new Error('Загрузка файлов временно недоступна'))) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.upload(
      canvas.getByLabelText('Файл для прикрепления'),
      new File(['pdf'], 'document.pdf', { type: 'application/pdf' }),
    )
    await expect(canvas.getByRole('alert')).toHaveTextContent('Загрузка файлов временно недоступна')
  },
}
export const Disabled: Story = { args: { disabled: true } }

export const DarkEnglish: Story = {
  globals: { theme: 'dark', locale: 'en', density: 'staff', motion: 'reduce' },
  decorators: [
    (Story) => (
      <div className="max-w-80">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole('button', { name: 'Attach file' })).toBeEnabled()
  },
}

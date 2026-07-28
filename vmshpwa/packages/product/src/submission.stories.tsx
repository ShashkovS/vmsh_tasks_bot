import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { AttachmentView } from './attachment'
import { SubmissionComposer } from './submission-composer'

const meta = { title: 'Product/Submission', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

function pagePreview(page: number, accent: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 320"><rect width="240" height="320" fill="#f7f4eb"/><path d="M24 56h192M24 92h160M24 128h192M24 164h145M24 235h192M24 271h130" stroke="#8f8b82" stroke-width="5" stroke-linecap="round"/><path d="M45 205c28-38 52-38 72 0s45 38 78-4" fill="none" stroke="${accent}" stroke-width="7"/><text x="205" y="300" text-anchor="end" font-family="sans-serif" font-size="24" fill="#3b3935">${page}</text></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

const seed: AttachmentView[] = [
  {
    id: 'p1',
    name: '1.jpg',
    sizeLabel: '1,2 МБ',
    status: 'ready',
    previewUrl: pagePreview(1, '#1b7f75'),
  },
  {
    id: 'p2',
    name: '2.jpg',
    sizeLabel: '1,1 МБ',
    status: 'uploading',
    progress: 60,
    previewUrl: pagePreview(2, '#6d5aa7'),
  },
  {
    id: 'p3',
    name: '3.jpg',
    sizeLabel: '1,1 МБ',
    status: 'failed',
    error: 'Не удалось загрузить',
    previewUrl: pagePreview(3, '#a84f65'),
  },
]

function ComposerHarness({
  offline = false,
  queued = false,
}: {
  offline?: boolean
  queued?: boolean
}) {
  const [text, setText] = useState('')
  const [items, setItems] = useState<AttachmentView[]>(seed)

  const move = (id: string, direction: -1 | 1) =>
    setItems((prev) => {
      const index = prev.findIndex((item) => item.id === id)
      const target = index + direction
      if (index < 0 || target < 0 || target >= prev.length) return prev
      const next = [...prev]
      const [moved] = next.splice(index, 1)
      next.splice(target, 0, moved!)
      return next
    })

  return (
    <div className="max-w-md">
      <SubmissionComposer
        attachments={items}
        draftSavedAt="12:08"
        offline={offline}
        onAddPhotos={() => undefined}
        onMoveDown={(id) => move(id, 1)}
        onMoveUp={(id) => move(id, -1)}
        onRemove={(id) => setItems((prev) => prev.filter((item) => item.id !== id))}
        onRetry={(id) =>
          setItems((prev) =>
            prev.map((item) =>
              item.id === id
                ? { ...item, status: 'uploading', progress: 5, error: undefined }
                : item,
            ),
          )
        }
        onRotate={(id) =>
          setItems((prev) =>
            prev.map((item) =>
              item.id === id
                ? { ...item, rotation: (((item.rotation ?? 0) + 90) % 360) as 0 | 90 | 180 | 270 }
                : item,
            ),
          )
        }
        onSubmit={() => undefined}
        onTextChange={setText}
        queued={queued}
        taskType="written"
        text={text}
        totalSizeLabel="3,4 МБ"
      />
    </div>
  )
}

export const Composer: Story = {
  name: 'Композер (текст + фото)',
  render: () => <ComposerHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    await userEvent.type(canvas.getByLabelText('Ваше решение'), 'Ответ: 89')
    await expect(canvas.getByLabelText('Ваше решение')).toHaveValue('Ответ: 89')

    // Переставить страницу 2 выше — она становится первой.
    await userEvent.click(canvas.getByRole('button', { name: 'Страница 2: выше' }))
    const items = canvas.getAllByRole('listitem')
    await expect(within(items[0]!).getByText('2.jpg')).toBeInTheDocument()

    // Повтор загрузки убирает ошибку.
    await userEvent.click(canvas.getByRole('button', { name: 'Повторить' }))
    await expect(canvas.queryByText('Не удалось загрузить')).not.toBeInTheDocument()
  },
}

export const Offline: Story = {
  name: 'Офлайн (очередь)',
  render: () => <ComposerHarness offline />,
}

export const Queued: Story = {
  name: 'Сохранено в очереди',
  render: () => <ComposerHarness offline queued />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByLabelText('Ваше решение')).toBeDisabled()
    await expect(canvas.getByRole('button', { name: 'Добавить фото' })).toBeDisabled()
    await expect(canvas.getByRole('button', { name: 'В очереди' })).toBeDisabled()
  },
}

export const OralWritten: Story = {
  name: 'Устная задача письменно',
  render: () => (
    <div className="max-w-md">
      <SubmissionComposer
        attachments={[]}
        draftSavedAt="19:02"
        onTextChange={() => undefined}
        taskType="oral"
        text=""
      />
    </div>
  ),
}

export const Closed: Story = {
  name: 'Приём закрыт',
  render: () => (
    <div className="max-w-md">
      <SubmissionComposer
        attachments={[
          {
            id: 'p1',
            name: '1.jpg',
            sizeLabel: '1,2 МБ',
            status: 'ready',
            previewUrl: pagePreview(1, '#1b7f75'),
          },
        ]}
        closed
        onTextChange={() => undefined}
        taskType="written"
        text="Ответ отправлен ранее."
      />
    </div>
  ),
}

import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { AttachmentView } from './attachment'
import { SubmissionComposer } from './submission-composer'
import { SubmissionReceipt } from './submission-receipt'

const meta = { title: 'Product/Submission', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const seed: AttachmentView[] = [
  { id: 'p1', name: '1.jpg', sizeLabel: '1,2 МБ', status: 'ready' },
  { id: 'p2', name: '2.jpg', sizeLabel: '1,1 МБ', status: 'uploading', progress: 60 },
  { id: 'p3', name: '3.jpg', sizeLabel: '1,1 МБ', status: 'failed', error: 'Не удалось загрузить' },
]

function ComposerHarness({ offline = false }: { offline?: boolean }) {
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
        attachments={[{ id: 'p1', name: '1.jpg', sizeLabel: '1,2 МБ', status: 'ready' }]}
        closed
        onTextChange={() => undefined}
        taskType="written"
        text="Ответ отправлен ранее."
      />
    </div>
  ),
}

export const Receipt: Story = {
  name: 'Квитанция о приёме',
  render: () => (
    <div className="max-w-md">
      <SubmissionReceipt
        clientTime="26 января, 12:08"
        reference="SUB-21н6-4f2a"
        serverTime="26 января, 12:08"
      />
    </div>
  ),
}

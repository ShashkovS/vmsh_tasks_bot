import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import {
  WrittenMaterialReassignment,
  type WrittenMaterialReassignmentPreviewView,
  type WrittenMaterialSelection,
} from './written-material-reassignment'

const meta = {
  title: 'Product/Review',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const materials = [
  {
    id: 'text-1',
    entryId: 'written-entry-1',
    itemKind: 'entry_text' as const,
    attachmentId: null,
    label: 'Сообщение ученика · 20:54',
    text: 'Эта работа относится к задаче про расстановку ладей.',
  },
  {
    id: 'photo-1',
    entryId: 'written-entry-1',
    itemKind: 'attachment' as const,
    attachmentId: 'written-attachment-1',
    label: 'Фотография · страница 1',
  },
  {
    id: 'photo-2',
    entryId: 'written-entry-1',
    itemKind: 'attachment' as const,
    attachmentId: 'written-attachment-2',
    label: 'Фотография · страница 2',
    locked: true,
  },
]

const targets = [
  {
    problemId: 'problem-41n-6',
    taskLabel: '41н.6 · Расстановка ладей',
    contextLabel: 'Математика 5–7 · Начинающие',
  },
  {
    problemId: 'problem-41p-4',
    taskLabel: '41п.4 · Ладьи и диагонали',
    contextLabel: 'Математика 5–7 · Продолжающие',
  },
]

function Harness({ postReview = false }: { postReview?: boolean }) {
  const [preview, setPreview] = useState<WrittenMaterialReassignmentPreviewView | null>(null)
  const [result, setResult] = useState('Перенос не выполнен')

  return (
    <div className="w-full max-w-4xl space-y-3">
      <WrittenMaterialReassignment
        initialSelectedIds={postReview ? ['photo-2'] : []}
        initialTargetProblemId={postReview ? targets[1]?.problemId : undefined}
        materials={materials}
        onConfirm={(targetProblemId, items, reason) =>
          setResult(
            `Перенесено ${items.length} → ${targetProblemId}${reason ? ` · ${reason}` : ''}`,
          )
        }
        onPreview={(targetProblemId, items: WrittenMaterialSelection[]) =>
          setPreview({ targetProblemId, postReview, selectedCount: items.length })
        }
        onResetPreview={() => setPreview(null)}
        preview={preview}
        sourceLabel="41н.5 · Метрический муравей"
        studentName="Анна Белова"
        targets={targets}
      />
      <p className="text-small text-muted-foreground" data-testid="readout" role="status">
        {result}
      </p>
    </div>
  )
}

export const MaterialReassignment: Story = {
  name: 'Исправление привязки материала',
  render: () => <Harness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('checkbox', { name: /Сообщение ученика/ }))
    await userEvent.click(canvas.getByRole('checkbox', { name: /Фотография · страница 1/ }))
    await userEvent.click(canvas.getByRole('combobox', { name: 'Целевая задача' }))
    await userEvent.click(within(document.body).getByText('41п.4 · Ладьи и диагонали'))
    await userEvent.type(
      canvas.getByRole('textbox', { name: /Причина для журнала/ }),
      'Выбран соседний номер.',
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить перенос' }))
    await expect(canvas.getByText(/Исходные сообщения, фотографии/)).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить перенос' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent(
      'Перенесено 2 → problem-41p-4 · Выбран соседний номер.',
    )
  },
}

export const MaterialReassignmentPostReview: Story = {
  name: 'Исправление после проверки',
  render: () => <Harness postReview />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить перенос' }))
    await expect(canvas.getByText(/Проверка уже началась/)).toBeInTheDocument()
    await expect(canvas.getByText('После проверки')).toBeInTheDocument()
  },
}

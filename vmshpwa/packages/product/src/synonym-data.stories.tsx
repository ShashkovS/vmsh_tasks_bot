import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { SynonymMergeSplitPreview, type SynonymProblemView } from './synonym-context'

const meta = {
  title: 'Product/Staff data',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const problems: SynonymProblemView[] = [
  {
    problemId: 'problem-math-41-b-6',
    courseName: 'Математика 5–7',
    groupName: 'Начинающие',
    lessonNumber: 41,
    taskNumber: '41н.6',
    title: 'Расстановка ладей',
    taskType: 'Письменная',
    submissionCount: 2,
    reviewCount: 1,
  },
  {
    problemId: 'problem-math-41-c-4',
    courseName: 'Математика 5–7',
    groupName: 'Продолжающие',
    lessonNumber: 41,
    taskNumber: '41п.4',
    title: 'Расстановка ладей',
    taskType: 'Тестовая',
    answerType: 'Натуральное число',
    submissionCount: 1,
    reviewCount: 0,
  },
]

function MergeSplitHarness() {
  const [mode, setMode] = useState<'merge' | 'split'>('merge')
  const [status, setStatus] = useState('Предпросмотр готов')
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-small"
          onClick={() => setMode('merge')}
          type="button"
        >
          Объединение
        </button>
        <button
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-small"
          onClick={() => setMode('split')}
          type="button"
        >
          Разделение
        </button>
      </div>
      <SynonymMergeSplitPreview
        mode={mode}
        onConfirm={() => setStatus(mode === 'merge' ? 'Связь подтверждена' : 'Связь снята')}
        problems={problems}
      />
      <p className="text-small text-muted-foreground" role="status">
        {status}
      </p>
    </div>
  )
}

export const SynonymMergeAndSplit: Story = {
  name: 'Synonym merge and split',
  render: () => <MergeSplitHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/problem_id/)).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Объединить' }))
    await expect(canvas.getByText('Связь подтверждена')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Разделение' }))
    await expect(canvas.getByText('Разделить задачи')).toBeInTheDocument()
  },
}

import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'

import { SynonymReviewCase } from './synonym-context'

const meta = {
  title: 'Product/Review',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const SynonymCombinedCase: Story = {
  name: 'Synonym combined case',
  render: () => (
    <SynonymReviewCase
      studentName="Анна Белова"
      submissions={[
        {
          id: 'sub-101',
          problemId: 'problem-math-41-b-6',
          courseName: 'Математика 5–7',
          groupName: 'Начинающие',
          taskNumber: '41н.6',
          submittedAt: '25 января, 20:54',
          body: 'Две фотографии исходного решения.',
        },
        {
          id: 'sub-114',
          problemId: 'problem-math-41-c-4',
          courseName: 'Математика 5–7',
          groupName: 'Продолжающие',
          taskNumber: '41п.4',
          submittedAt: '26 января, 10:03',
          body: 'Текстовое дополнение и ещё одна фотография.',
          latest: true,
        },
      ]}
      taskTitle="Расстановка ладей"
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('2 посылки объединены')).toBeInTheDocument()
    await expect(
      canvas.getByText(/Вердикт будет записан в Математика 5–7 · Продолжающие · 41п\.4/),
    ).toBeInTheDocument()
  },
}

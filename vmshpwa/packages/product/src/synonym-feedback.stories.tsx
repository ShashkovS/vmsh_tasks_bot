import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'

import { SynonymMergedTimeline as SynonymMergedTimelineView } from './synonym-context'

const meta = {
  title: 'Product/Feedback',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const SynonymMergedTimeline: Story = {
  name: 'Synonym merged timeline',
  render: () => (
    <SynonymMergedTimelineView
      messages={[
        {
          id: 'beginner-submission',
          author: { kind: 'student', name: 'Анна' },
          at: '25 января, 20:54',
          channel: 'pwa',
          origin: {
            courseName: 'Математика 5–7',
            groupName: 'Начинающие',
            taskNumber: '41н.6',
          },
          body: 'Сначала выбрала строки и столбцы. На фотографии — полный подсчёт.',
          own: true,
        },
        {
          id: 'beginner-review',
          author: { kind: 'teacher', name: 'М. Иванова' },
          at: '26 января, 09:12',
          channel: 'pwa',
          origin: {
            courseName: 'Математика 5–7',
            groupName: 'Начинающие',
            taskNumber: '41н.6',
          },
          body: 'Идея верная, но объясните, почему ладьи не бьют друг друга.',
        },
        {
          id: 'continuing-resubmission',
          author: { kind: 'student', name: 'Анна' },
          at: '26 января, 10:03',
          channel: 'pwa',
          origin: {
            courseName: 'Математика 5–7',
            groupName: 'Продолжающие',
            taskNumber: '41п.4',
          },
          body: 'Дописала объяснение в доступном листке продолжающих.',
          own: true,
        },
      ]}
      status="Нужно дополнить"
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByText(/41н\.6/)).toHaveLength(2)
    await expect(canvas.getByText(/41п\.4/)).toBeInTheDocument()
    await expect(canvas.queryByRole('tab')).not.toBeInTheDocument()
  },
}

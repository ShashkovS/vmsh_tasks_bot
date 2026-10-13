import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import type { StatisticsPlusTable } from '@vmsh/contracts'
import { PlusMatrix } from './staff-statistics-reports'

// Representative cells receive the full axe audit; 700 rows are exercised by E2E.
const data: StatisticsPlusTable = {
  schemaVersion: 1,
  courses: [],
  selectedCourseId: 'c-1',
  selectedGroupId: 'g-1',
  requestId: 'story',
  lessonNumbers: [0],
  lessonNumber: 0,
  problems: Array.from({ length: 20 }, (_, i) => ({
    problemId: `p-${i + 1}`,
    label: String(i + 1),
    title: `Задача ${i + 1}`,
  })),
  rows: Array.from({ length: 4 }, (_, i) => ({
    studentId: `u-${i + 1}`,
    name: `Школьник ${String(i + 1).padStart(3, '0')} Тестовый`,
    total: 17.5,
    cells: Array.from({ length: 20 }, (_, j) => ({
      score: j === 2 || j === 3 ? 0 : j === 0 ? 0.5 : 1,
      source: j === 3 ? null : (['bot', 'written', 'zoom', 'school'] as const)[j % 4]!,
      attempted: j !== 3,
      pending: j === 1,
    })),
  })),
}
const meta = {
  title: 'Pages/Staff/Plus matrix',
  component: PlusMatrix,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <div className="staff-statistics p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PlusMatrix>
export default meta
type Story = StoryObj<typeof meta>
export const Sources: Story = {
  args: { data },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvasElement.querySelectorAll('tbody tr')).toHaveLength(4)
    await expect(canvas.getAllByRole('columnheader')).toHaveLength(22)
  },
}
export const Empty: Story = { args: { data: { ...data, rows: [] } } }

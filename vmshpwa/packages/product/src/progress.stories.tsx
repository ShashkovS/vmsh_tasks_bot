import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import { DistributionViolin, TrendWithBand, type TrendPoint } from './progress-charts'
import { StudentProgress } from './student-progress'

const meta = { title: 'Product/Progress', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const groupScores = [
  0, 0.25, 0.5, 0.5, 0.7, 0.7, 0.7, 0.95, 1, 0.7, 0.5, 0.95, 0.7, 0.25, 0.5, 0.7, 1, 0.95, 0.7, 0.5,
]

const trend: TrendPoint[] = [
  { label: 'Зан. 1', value: 2, lower: 1, upper: 3 },
  { label: 'Зан. 2', value: 3, lower: 2, upper: 4 },
  { label: 'Зан. 3', value: 5, lower: 3, upper: 6 },
  { label: 'Зан. 4', value: 6, lower: 5, upper: 8 },
]

export const Charts: Story = {
  name: 'Графики: распределение и динамика',
  render: () => (
    <div className="flex flex-wrap gap-8">
      <DistributionViolin
        caption="Распределение баллов по группе."
        domain={[0, 1]}
        self={0.7}
        values={groupScores}
      />
      <TrendWithBand caption="Динамика с доверительной полосой." domain={[0, 8]} points={trend} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Чарт имеет текстовую альтернативу (accessible name).
    await expect(canvas.getByRole('img', { name: /Распределение по группе/ })).toBeInTheDocument()

    // И табличный эквивалент.
    const summaries = canvas.getAllByText('Показать числами')
    await userEvent.click(summaries[0]!)
    await expect(canvas.getByText('Медиана')).toBeInTheDocument()
  },
}

export const Personal: Story = {
  name: 'Личный прогресс',
  render: () => (
    <div className="max-w-sm">
      <StudentProgress
        achievements={['Первая задача сдана', 'Неделя без пропусков']}
        attemptedCount={5}
        distribution={{ values: groupScores, self: 0.7 }}
        solvedCount={3}
        streakDays={4}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    // Слова, не рейтинг.
    await expect(canvas.getByText(/задачи зачтено/)).toBeInTheDocument()
    // Распределение по группе спрятано за закрытым раскрытием, не навязывается.
    const summary = canvas.getByText('Посмотреть, как решала вся группа')
    await expect(summary.closest('details')).not.toHaveAttribute('open')
  },
}

export const EmptyState: Story = {
  name: 'Пустое состояние',
  render: () => (
    <div className="max-w-sm">
      <StudentProgress solvedCount={0} />
    </div>
  ),
}

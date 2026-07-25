import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import {
  DistributionViolin,
  StrengthTrend,
  TrendWithBand,
  type StrengthLessonPoint,
  type TrendPoint,
} from './progress-charts'
import { StudentProgress } from './student-progress'

const meta = { title: 'Product/Progress', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const groupScores = [
  0, 0.25, 0.5, 0.5, 0.7, 0.7, 0.7, 0.95, 1, 0.7, 0.5, 0.95, 0.7, 0.25, 0.5, 0.7, 1, 0.95, 0.7, 0.5,
]

// Личная динамика «насколько получается», по образцу a21_create_plots.py.
const lessons: StrengthLessonPoint[] = [
  {
    lesson: '1',
    simple: 7.3,
    complex: 2.6,
    simpleSmooth: 8.6,
    complexSmooth: 4.4,
    difficulty: 7.6,
    solved: '6/12',
    group: 'п',
  },
  {
    lesson: '2',
    simple: 9.3,
    complex: 4.0,
    simpleSmooth: 8.7,
    complexSmooth: 4.6,
    difficulty: 6.7,
    solved: '11/14',
    group: 'п',
  },
  {
    lesson: '3',
    simple: 9.0,
    complex: 5.6,
    simpleSmooth: 8.6,
    complexSmooth: 4.5,
    difficulty: 7.8,
    solved: '12/15',
    group: 'п',
  },
  {
    lesson: '4',
    simple: 8.3,
    complex: 5.3,
    simpleSmooth: 8.4,
    complexSmooth: 4.3,
    difficulty: 7.2,
    solved: '11/14',
    group: 'п',
  },
  {
    lesson: '5',
    simple: 8.3,
    complex: 5.0,
    simpleSmooth: 8.3,
    complexSmooth: 4.2,
    difficulty: 7.8,
    solved: '12/17',
    group: 'п',
  },
  {
    lesson: '6',
    simple: 9.9,
    complex: 6.6,
    simpleSmooth: 8.5,
    complexSmooth: 4.6,
    difficulty: 6.6,
    solved: '13/13',
    group: 'п',
  },
  {
    lesson: '7',
    simple: 9.3,
    complex: 5.2,
    simpleSmooth: 8.2,
    complexSmooth: 4.2,
    difficulty: 7.7,
    solved: '11/14',
    group: 'п',
  },
  {
    lesson: '8',
    simple: 5.6,
    complex: 2.0,
    simpleSmooth: 7.9,
    complexSmooth: 4.1,
    difficulty: 8.0,
    solved: '7/19',
    group: 'п',
  },
]

const trend: TrendPoint[] = [
  { label: 'Зан. 1', value: 2, lower: 1, upper: 3 },
  { label: 'Зан. 2', value: 3, lower: 2, upper: 4 },
  { label: 'Зан. 3', value: 5, lower: 3, upper: 6 },
  { label: 'Зан. 4', value: 6, lower: 5, upper: 8 },
]

export const Charts: Story = {
  name: 'Графики: группа и личная динамика',
  render: () => (
    <div className="space-y-8">
      <DistributionViolin
        caption="Распределение баллов по группе."
        domain={[0, 1]}
        values={groupScores}
      />
      <StrengthTrend
        caption="Насколько получается решать простые и сложные задачи. Это личная динамика — с другими не сравниваем."
        points={lessons}
      />
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

export const ConfidenceBand: Story = {
  name: 'Линия с доверительной полосой (общий примитив)',
  render: () => (
    <div className="max-w-md">
      <TrendWithBand caption="Динамика с доверительной полосой." domain={[0, 8]} points={trend} />
    </div>
  ),
}

export const Personal: Story = {
  name: 'Личный прогресс',
  render: () => (
    <div className="max-w-sm">
      <StudentProgress
        achievements={['Первая задача сдана', 'Неделя без пропусков']}
        attemptedCount={5}
        distribution={{ values: groupScores }}
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

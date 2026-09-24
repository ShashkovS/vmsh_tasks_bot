import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import {
  DistributionViolin,
  StrengthTrend,
  TrendWithBand,
  type StrengthLessonPoint,
  type TrendPoint,
} from './progress-charts'
import { ActivityCalendar } from './activity-calendar'
import { StudentProgress } from './student-progress'

const meta = { title: 'Product/Progress', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const FractionalLessonDistributions: Story = {
  render: () => (
    <div className="flex gap-4">
      <DistributionViolin
        values={[0, 0.5, 1, 1.5, 2]}
        domain={[0, 3]}
        colorIndex={1}
        caption="Начинающие · баллы"
      />
      <DistributionViolin
        values={[0, 1, 1.5, 2.5, 3]}
        domain={[0, 3]}
        colorIndex={2}
        caption="Продолжающие · баллы"
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByRole('img')).toHaveLength(2)
    await expect(canvas.getAllByText('0,5')).toHaveLength(2)
  },
}

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
  name: 'Staff-агрегат и отдельная личная динамика',
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
        solvedCount={3}
        streakDays={4}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    // Слова, не рейтинг.
    await expect(canvas.getByText(/задачи зачтено/)).toBeInTheDocument()
    // Личный компонент принципиально не получает распределение группы.
    await expect(canvas.queryByText(/группа|медиана|процентиль/i)).not.toBeInTheDocument()
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

export const Activity: Story = {
  name: 'Календарь личной активности',
  render: () => (
    <div className="max-w-xl">
      <ActivityCalendar
        days={[
          { date: '2026-01-12', problemCount: 1 },
          { date: '2026-01-13', problemCount: 2 },
          { date: '2026-01-17', problemCount: 5 },
          { date: '2026-01-22', problemCount: 3 },
          { date: '2026-01-29', problemCount: 1 },
        ]}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('5 дней работы · 12 задач')).toBeInTheDocument()
    await userEvent.click(canvas.getByText('Показать по датам'))
    await expect(canvas.getByText(/12 янв/)).toBeInTheDocument()
  },
}

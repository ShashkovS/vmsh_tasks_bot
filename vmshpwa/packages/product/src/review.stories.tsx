import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { FeedbackThread } from './feedback-thread'
import { ReviewFeedbackForm } from './review-feedback-form'
import { ReviewLock } from './review-lock'
import { ReviewQueue, type ReviewQueueItem, type ReviewSort } from './review-queue'
import { ThreePaneReview } from './three-pane-review'
import type { LevelView } from './types'
import { fullVerdictScale } from './verdict-registry'

const meta = { title: 'Product/Review', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const beginner: LevelView = { code: 'н', name: 'Начинающие', colorIndex: 1 }
const continuing: LevelView = { code: 'п', name: 'Продолжающие', colorIndex: 2 }

const items: ReviewQueueItem[] = [
  {
    id: '1',
    taskNumber: '21н.6',
    taskTitle: 'Расстановка ладей',
    level: beginner,
    studentName: 'Аня',
    groupName: 'Начинающие',
    waitingLabel: '3 ч 20 мин',
    waitingMinutes: 200,
  },
  {
    id: '2',
    taskNumber: '21н.1',
    taskTitle: 'Разнообразные вагоны',
    level: beginner,
    studentName: 'Боря',
    groupName: 'Начинающие',
    waitingLabel: '2 ч 10 мин',
    waitingMinutes: 130,
  },
  {
    id: '3',
    taskNumber: '21н.7',
    taskTitle: 'Крылья бабочки',
    level: continuing,
    studentName: 'Вика',
    groupName: 'Продолжающие',
    waitingLabel: '45 мин',
    waitingMinutes: 45,
    busyBy: 'И. Соколов',
  },
  {
    id: '4',
    taskNumber: '21н.8',
    taskTitle: 'Пример на вычитание',
    level: continuing,
    studentName: 'Гена',
    groupName: 'Продолжающие',
    waitingLabel: '15 мин',
    waitingMinutes: 15,
    reviewed: true,
  },
]

function QueueHarness() {
  const [sort, setSort] = useState<ReviewSort>('task')
  const [opened, setOpened] = useState<string | null>(null)
  return (
    <div className="space-y-2">
      <ReviewQueue
        items={items}
        mode="list"
        onModeChange={() => undefined}
        onOpen={setOpened}
        onRecheck={() => undefined}
        onSortChange={setSort}
        sort={sort}
      />
      <p className="text-small text-muted-foreground" data-testid="readout" role="status">
        {opened ? `Открыта работа ${opened}` : 'Работа не открыта'}
      </p>
    </div>
  )
}

export const Queue: Story = {
  name: 'Очередь проверки',
  render: () => <QueueHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Сортировка по умолчанию — по задаче: первым идёт 21н.1 (Боря).
    let rows = canvas.getAllByRole('row')
    await expect(within(rows[1]!).getByText('Боря')).toBeInTheDocument()

    // Сортировка по ожиданию поднимает дольше всех ждущего (Аня, 200 мин).
    await userEvent.click(canvas.getByRole('button', { name: /Ждёт/ }))
    rows = canvas.getAllByRole('row')
    await expect(within(rows[1]!).getByText('Аня')).toBeInTheDocument()

    // Занятая работа не открывается кнопкой.
    await expect(canvas.getByText('Проверяет И. Соколов')).toBeInTheDocument()
  },
}

function FormHarness() {
  const [result, setResult] = useState('')
  return (
    <div className="max-w-md space-y-3">
      <ReviewFeedbackForm
        onSubmit={(value) =>
          setResult(
            `Отправлено: ${value.verdict.value}${value.comment ? ` — ${value.comment}` : ''}`,
          )
        }
        verdicts={fullVerdictScale}
      />
      <p className="text-small text-muted-foreground" data-testid="readout" role="status">
        {result || 'Не отправлено'}
      </p>
    </div>
  )
}

export const FeedbackPlus: Story = {
  name: 'Вердикт «+» цифрой, без подтверждения',
  render: () => <FormHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    // Цифра 1 всегда «+» (лучший вердикт).
    await userEvent.keyboard('1')
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить вердикт' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Отправлено: plus')
  },
}

export const FeedbackGuard: Story = {
  name: 'Незачёт без комментария — подтверждение',
  render: () => <FormHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    // Цифра 3 — вердикт ниже «Зачтено» (вес 0.7); «+.» (0.95) уже зачтено и не переспрашивает.
    await userEvent.keyboard('3')
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить вердикт' }))
    await expect(canvas.getByText(/Незачёт без комментария/)).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить всё равно' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Отправлено:')
  },
}

export const Lock: Story = {
  name: 'Состояния аренды',
  render: () => (
    <div className="max-w-md space-y-3">
      <ReviewLock expiresInLabel="осталось 24 мин" state="held" />
      <ReviewLock holderName="И. Соколов" state="busy" />
      <ReviewLock onRefetch={() => undefined} state="lost" />
    </div>
  ),
}

function WorkspaceHarness() {
  const [sort, setSort] = useState<ReviewSort>('waiting')
  return (
    <ThreePaneReview
      discussion={
        <section className="space-y-2" aria-label="Обсуждение работы">
          <h3 className="text-label font-medium text-foreground">Обсуждение</h3>
          <FeedbackThread
            messages={[
              {
                id: 'student-1',
                author: { kind: 'student', name: 'Аня' },
                at: '12:08',
                channel: 'pwa',
                body: 'Я сначала рассмотрела случай k = n.',
              },
              {
                id: 'student-2',
                author: { kind: 'student', name: 'Аня' },
                at: '12:11',
                channel: 'pwa',
                body: 'И ещё дослала пояснение для k = 1.',
              },
            ]}
          />
        </section>
      }
      evidence={
        <div className="space-y-2 rounded-md border border-paper-edge bg-paper p-4 font-reading text-small text-foreground">
          <p className="text-caption text-muted-foreground">Полученная работа · изменить нельзя</p>
          <p>Пусть на доске n×n стоят ладьи, не бьющие друг друга.</p>
          <p>Тогда в каждой строке не более одной ладьи, значит ответ n! при k = n.</p>
        </div>
      }
      feedback={<ReviewFeedbackForm onSubmit={() => undefined} verdicts={fullVerdictScale} />}
      queue={
        <ReviewQueue
          items={items.slice(0, 3)}
          mode="fast"
          onModeChange={() => undefined}
          onOpen={() => undefined}
          onSortChange={setSort}
          sort={sort}
        />
      }
    />
  )
}

export const Workspace: Story = {
  name: 'Рабочее место: работа → обсуждение → ответ',
  parameters: { layout: 'fullscreen' },
  render: () => (
    <div className="p-4">
      <WorkspaceHarness />
    </div>
  ),
}

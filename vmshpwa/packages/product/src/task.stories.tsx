import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { DeadlineNotice } from './deadline-notice'
import { LevelChip } from './level-chip'
import { TaskListItem } from './task-list-item'
import { taskTypeName, TaskTypeIcon } from './task-type'
import type { LevelView, TaskListItemView, TaskType } from './types'
import { VerdictMark } from './verdict-mark'
import {
  binaryVerdictScale,
  findVerdict,
  fullVerdictScale,
  ternaryVerdictScale,
} from './verdict-registry'

const meta = { title: 'Product/Task', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const levels: LevelView[] = [
  { code: 'н', name: 'Начинающие', colorIndex: 1 },
  { code: 'п2', name: 'Продолжающие', colorIndex: 2 },
  { code: 'dp2', name: 'Эксперты', colorIndex: 3 },
  { code: 'i9a', name: 'Тестирование', colorIndex: 0 },
]

export const Levels: Story = {
  name: 'Уровень (слово + компактный)',
  render: () => (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {levels.map((level) => (
          <LevelChip key={level.code} level={level} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-label text-muted-foreground">
          Компактный (Staff, имя в подсказке):
        </span>
        {levels.map((level) => (
          <LevelChip compact key={level.code} level={level} />
        ))}
      </div>
    </div>
  ),
}

const aiVerdict = { ...findVerdict(fullVerdictScale, 'minus-plus')!, provenance: 'ai' as const }

export const Verdicts: Story = {
  name: 'Вердикты и шкалы курса',
  render: () => (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {fullVerdictScale.map((verdict) => (
          <VerdictMark key={verdict.value} showLabel verdict={verdict} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <VerdictMark showLabel verdict={aiVerdict} />
        <span className="text-label text-muted-foreground">
          — оценка ИИ визуально отделена от живого преподавателя
        </span>
      </div>
      <dl className="space-y-2 text-small">
        {[
          ['Бинарная', binaryVerdictScale],
          ['Трёхступенчатая', ternaryVerdictScale],
          ['Полная', fullVerdictScale],
        ].map(([name, scale]) => (
          <div className="flex flex-wrap items-center gap-2" key={name as string}>
            <dt className="w-40 text-muted-foreground">{name as string}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {(scale as typeof fullVerdictScale).map((verdict) => (
                <VerdictMark key={verdict.value} verdict={verdict} />
              ))}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  ),
}

export const Types: Story = {
  name: 'Типы задач и дедлайн',
  render: () => (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        {(['test', 'written', 'oral'] as TaskType[]).map((type) => (
          <span className="inline-flex items-center gap-2 text-small" key={type}>
            <TaskTypeIcon type={type} />
            {taskTypeName(type)}
          </span>
        ))}
      </div>
      <DeadlineNotice
        absoluteLabel="воскресенья, 1 февраля, 13:00"
        closesAt="2026-02-01T10:00:00Z"
        relativeLabel="осталось 5 дней"
      />
      <DeadlineNotice
        absoluteLabel="сегодня, 19:00"
        closesAt="2026-01-26T16:00:00Z"
        relativeLabel="осталось 40 минут"
        state="closing-soon"
      />
      <DeadlineNotice
        absoluteLabel="воскресенья, 1 февраля, 13:00"
        closesAt="2026-02-01T10:00:00Z"
        relativeLabel="решения опубликованы"
        state="closed"
      />
    </div>
  ),
}

const tasks: TaskListItemView[] = [
  {
    id: '1',
    number: '21н.1',
    title: 'Разнообразные вагоны',
    type: 'test',
    status: { kind: 'accepted', label: 'Зачтено', tone: 'success' },
    verdict: findVerdict(fullVerdictScale, 'plus')!,
  },
  {
    id: '6',
    number: '21н.6',
    title: 'Расстановка ладей',
    type: 'written',
    status: { kind: 'checking', label: 'На проверке', tone: 'info' },
    hasNewFeedback: true,
  },
  {
    id: '7',
    number: '21н.7',
    title: 'Крылья бабочки',
    type: 'written',
    status: { kind: 'needs-work', label: 'Нужна доработка', tone: 'warning' },
    verdict: findVerdict(fullVerdictScale, 'plus-minus')!,
  },
  {
    id: '8',
    number: '21н.8',
    title: 'Пример на вычитание',
    type: 'oral',
    status: { kind: 'not-started', label: 'Не начата', tone: 'neutral' },
  },
]

function TaskList() {
  const [opened, setOpened] = useState<string | null>(null)
  return (
    <div className="max-w-md space-y-2">
      <ul className="space-y-2">
        {tasks.map((task) => (
          <li key={task.id}>
            <TaskListItem onOpen={setOpened} task={task} />
          </li>
        ))}
      </ul>
      <p className="text-small text-muted-foreground" role="status">
        {opened ? `Открыта задача ${opened}` : 'Задача не открыта'}
      </p>
    </div>
  )
}

export const List: Story = {
  name: 'Список задач',
  render: () => <TaskList />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Вердикт доступен screen reader словами, тип — доступным именем иконки.
    await expect(canvas.getByText('Зачтено')).toBeInTheDocument()
    await expect(canvas.getAllByLabelText('Письменная задача').length).toBeGreaterThan(0)

    // Открытие задачи вызывает onOpen.
    await userEvent.click(canvas.getByRole('button', { name: /Расстановка ладей/ }))
    await expect(canvas.getByRole('status')).toHaveTextContent('Открыта задача 6')
  },
}

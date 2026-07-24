import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { BroadcastComposer, ClassroomPlanner, SosQueue, type SosItem } from './staff-outreach'
import {
  LatexUpload,
  MissingAssetsFlow,
  PublicationControl,
  type PublicationLevelRow,
} from './staff-publishing'
import type { LevelView } from './types'

const meta = { title: 'Product/Staff admin', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const beginner: LevelView = { code: 'н', name: 'Начинающие', colorIndex: 1 }
const continuing: LevelView = { code: 'п', name: 'Продолжающие', colorIndex: 2 }

const pubRows: PublicationLevelRow[] = [
  { level: beginner, task: 'draft', hint: 'draft', solution: 'none' },
  {
    level: continuing,
    task: 'published',
    hint: 'published',
    solution: 'scheduled',
    scheduledAt: '1 фев, 13:00',
  },
]

export const Publication: Story = {
  name: 'Публикация по уровням',
  render: () => {
    function Harness() {
      const [readout, setReadout] = useState('—')
      return (
        <div className="space-y-2">
          <PublicationControl
            onPublish={(code) => setReadout(`Опубликован уровень ${code}`)}
            onRollback={(code) => setReadout(`Откачен уровень ${code}`)}
            rows={pubRows}
          />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {readout}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Опубликовать' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Опубликован уровень н')
  },
}

export const Broadcast: Story = {
  name: 'Рассылка',
  render: () => {
    function Harness() {
      const [readout, setReadout] = useState('—')
      return (
        <div className="space-y-2">
          <BroadcastComposer
            audiencePresets={[
              { id: 'beginners', label: 'Начинающие', count: 42 },
              { id: 'all', label: 'Все ученики', count: 150 },
            ]}
            onDryRun={() => setReadout('Пробный прогон запущен')}
            onSend={() => setReadout('Отправлено')}
          />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {readout}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Сообщение'), 'Занятие в субботу!')
    await userEvent.click(canvas.getByRole('button', { name: 'Пробный прогон' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Пробный прогон запущен')
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить…' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Отправлено')
  },
}

const sosItems: SosItem[] = [
  {
    id: 'q1',
    studentName: 'Аня',
    taskNumber: '21н.6',
    question: 'Не понимаю, как считать число расстановок для k = 1.',
    at: '12:20',
    status: 'open',
  },
  {
    id: 'q2',
    studentName: 'Боря',
    question: 'Спасибо, разобрался!',
    at: '11:05',
    status: 'answered',
  },
]

export const Sos: Story = {
  name: 'Вопросы и SOS',
  render: () => {
    function Harness() {
      const [readout, setReadout] = useState('—')
      return (
        <div className="max-w-lg space-y-2">
          <SosQueue items={sosItems} onOpen={(id) => setReadout(`Открыт вопрос ${id}`)} />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {readout}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Ответить' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Открыт вопрос q1')
  },
}

export const Latex: Story = {
  name: 'Загрузка LaTeX',
  render: () => (
    <div className="max-w-lg">
      <LatexUpload
        files={[
          { id: 'f1', name: '21н.tex', status: 'done' },
          { id: 'f2', name: '21п.tex', status: 'processing', progress: 55 },
          {
            id: 'f3',
            name: '21х.tex',
            status: 'error',
            diagnostics: ['Строка 42: неизвестная команда \\tikzz', 'Нет файла рисунка fig3.svg'],
          },
        ]}
        onRetry={() => undefined}
        sourcePreview={'\\begin{problem}\n  n^2 + 179 = k^2\n\\end{problem}'}
      />
    </div>
  ),
}

export const MissingAssets: Story = {
  name: 'Недостающие ресурсы',
  render: () => (
    <div className="max-w-lg">
      <MissingAssetsFlow
        assets={[
          {
            id: 'a1',
            ref: 'fig3.svg',
            candidates: [
              { id: 'c1', label: 'fig3_v2.svg' },
              { id: 'c2', label: 'rooks.svg' },
            ],
          },
          { id: 'a2', ref: 'table7.svg' },
        ]}
        onReuse={() => undefined}
        onUpload={() => undefined}
      />
    </div>
  ),
}

export const Planner: Story = {
  name: 'Распределение по кабинетам',
  render: () => (
    <ClassroomPlanner
      conflicts={['Вика записана в две группы одновременно.']}
      onMove={() => undefined}
      rooms={[
        { id: 'r1', name: 'Кабинет 305', capacity: 3, assigned: ['Аня', 'Боря'] },
        { id: 'r2', name: 'Кабинет 307', capacity: 2, assigned: ['Вика', 'Гена', 'Дима'] },
      ]}
      unassigned={['Егор']}
    />
  ),
}

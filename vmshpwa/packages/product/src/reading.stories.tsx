import type { Meta, StoryObj } from '@storybook/react-vite'
import { Lightbulb } from 'lucide-react'
import { expect, userEvent, within } from 'storybook/test'

import { ConsciousDisclosure, HintDisclosure, SolutionDisclosure } from './conscious-disclosure'
import { DeadlineNotice } from './deadline-notice'
import { ProblemHeader } from './problem-header'
import type { LevelView } from './types'
import { ZoomableFigure } from './zoomable-figure'

const meta = { title: 'Product/Reading', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const beginner: LevelView = { code: 'н', name: 'Начинающие', colorIndex: 1 }

/* A small chessboard figure (n = 4) with two non-attacking rooks. */
function RooksBoard() {
  const cells = 4
  const size = 44
  return (
    <svg
      aria-hidden="true"
      height={cells * size}
      role="presentation"
      viewBox={`0 0 ${cells * size} ${cells * size}`}
      width={cells * size}
      xmlns="http://www.w3.org/2000/svg"
    >
      {Array.from({ length: cells }, (_, row) =>
        Array.from({ length: cells }, (_, col) => (
          <rect
            className={(row + col) % 2 === 0 ? 'fill-paper' : 'fill-surface-sunken'}
            height={size}
            key={`${row}-${col}`}
            width={size}
            x={col * size}
            y={row * size}
          />
        )),
      )}
      <rect
        className="fill-none stroke-paper-edge"
        height={cells * size}
        strokeWidth={1.5}
        width={cells * size}
        x={0}
        y={0}
      />
      {(
        [
          [0, 0],
          [2, 1],
        ] as Array<[number, number]>
      ).map(([r, c]) => (
        <text
          className="fill-foreground"
          dominantBaseline="central"
          fontSize={30}
          key={`${r}-${c}`}
          textAnchor="middle"
          x={c * size + size / 2}
          y={r * size + size / 2}
        >
          ♜
        </text>
      ))}
    </svg>
  )
}

export const Header: Story = {
  name: 'Заголовок задачи',
  render: () => (
    <article className="max-w-2xl">
      <ProblemHeader
        deadline={
          <DeadlineNotice
            absoluteLabel="воскресенья, 1 февраля, 13:00"
            closesAt="2026-02-01T10:00:00Z"
            relativeLabel="осталось 5 дней"
          />
        }
        level={beginner}
        number="21н.6"
        onShowHistory={() => undefined}
        title="Расстановка ладей"
        type="written"
      />
    </article>
  ),
}

export const Figure: Story = {
  name: 'Масштабируемый рисунок',
  render: () => (
    <div className="max-w-sm">
      <ZoomableFigure
        alt="Шахматная доска четыре на четыре, две ладьи не бьют друг друга"
        caption="Рис. 1. Одна из расстановок для n = 4."
      >
        <RooksBoard />
      </ZoomableFigure>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const value = canvas.getByTestId('zoom-value')
    await expect(value).toHaveTextContent('100%')

    await userEvent.click(canvas.getByRole('button', { name: 'Увеличить' }))
    await expect(value).toHaveTextContent('150%')

    await userEvent.click(canvas.getByRole('button', { name: 'Сбросить масштаб' }))
    await expect(value).toHaveTextContent('100%')
  },
}

export const Disclosure: Story = {
  name: 'Подсказка и решение',
  render: () => (
    <div className="max-w-xl space-y-2">
      <HintDisclosure meta="от 28 января">
        Сколько ладей помещается в одну строку? А как связаны строки и столбцы?
      </HintDisclosure>
      <SolutionDisclosure>
        Каждая строка и каждый столбец содержит не более одной ладьи, поэтому расстановка задаёт
        частичную биекцию между строками и столбцами. Для k ладей выбираем k строк, k столбцов и
        взаимно однозначное соответствие между ними.
      </SolutionDisclosure>
      <SolutionDisclosure lockedNote="откроется после дедлайна">не показывается</SolutionDisclosure>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Решение скрыто, пока его осознанно не открыли.
    await expect(canvas.queryByText(/частичную биекцию/)).not.toBeInTheDocument()

    await userEvent.click(canvas.getByRole('button', { name: /^Решение/ }))
    // Появляется подтверждение, а не сразу текст.
    await expect(canvas.getByText('Открыть решение?')).toBeInTheDocument()
    await expect(canvas.queryByText(/частичную биекцию/)).not.toBeInTheDocument()

    await userEvent.click(canvas.getByRole('button', { name: 'Показать решение' }))
    await expect(canvas.getByText(/частичную биекцию/)).toBeInTheDocument()

    // Заблокированное решение остаётся заблокированным.
    await expect(canvas.getByText('откроется после дедлайна')).toBeInTheDocument()
    await expect(canvas.queryByText('не показывается')).not.toBeInTheDocument()
  },
}

export const TaskReading: Story = {
  name: 'Чтение задачи целиком',
  render: () => (
    <article className="mx-auto max-w-2xl space-y-5">
      <ProblemHeader
        deadline={
          <DeadlineNotice
            absoluteLabel="воскресенья, 1 февраля, 13:00"
            closesAt="2026-02-01T10:00:00Z"
            relativeLabel="осталось 5 дней"
          />
        }
        level={beginner}
        number="21н.6"
        onShowHistory={() => undefined}
        title="Расстановка ладей"
        type="written"
      />

      <div className="space-y-3 font-reading text-reading leading-relaxed text-foreground">
        <p>
          На доске n×n расставляют ладьи так, чтобы никакие две не били друг друга. Найдите число
          способов расставить ровно k ладей.
        </p>
        <p>Разберите случай k = n и объясните, почему ответ равен n!.</p>
      </div>

      <ZoomableFigure
        alt="Шахматная доска четыре на четыре, две ладьи не бьют друг друга"
        caption="Рис. 1. Одна из расстановок для n = 4."
      >
        <RooksBoard />
      </ZoomableFigure>

      <div className="space-y-2">
        <HintDisclosure meta="от 28 января">
          Посчитайте отдельно выбор строк, выбор столбцов и способ их сопоставить.
        </HintDisclosure>
        <ConsciousDisclosure
          confirm={{
            title: 'Открыть решение?',
            body: 'Решение нельзя «развидеть». Открывайте, только если действительно застряли.',
            action: 'Показать решение',
          }}
          icon={Lightbulb}
          label="Решение"
        >
          Для k ладей: C(n, k) способов выбрать строки, C(n, k) — столбцы и k! сопоставлений, итого
          C(n, k)² · k!. При k = n получаем n!.
        </ConsciousDisclosure>
      </div>
    </article>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Условие всегда перед глазами — до любых раскрытий.
    await expect(canvas.getByText(/никакие две не били друг друга/)).toBeInTheDocument()

    // Раскрытие подсказки: подтверждение → текст, условие остаётся на месте.
    await userEvent.click(canvas.getByRole('button', { name: /^Подсказка/ }))
    await userEvent.click(canvas.getByRole('button', { name: 'Показать подсказку' }))
    await expect(canvas.getByText(/выбор строк/)).toBeInTheDocument()
    await expect(canvas.getByText(/никакие две не били друг друга/)).toBeInTheDocument()
  },
}

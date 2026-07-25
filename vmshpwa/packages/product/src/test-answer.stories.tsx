import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { AnswerSpec } from './answer-spec'
import { TestAnswer } from './test-answer'

// Proof for dev/design-system/06-storybook-and-testing.md: partial input stays
// calm; format feedback appears only after the student leaves the whole control.

const meta = { title: 'Product/Test answer', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

function Harness({ spec, label }: { spec: AnswerSpec; label?: string }) {
  const [value, setValue] = useState('')
  return (
    <div className="max-w-sm space-y-3">
      <TestAnswer label={label} onChange={setValue} spec={spec} />
      <output className="sr-only" data-testid="answer">
        {value || '—'}
      </output>
    </div>
  )
}

export const Scalar: Story = {
  name: 'Скаляр · ошибка формата',
  render: () => (
    <Harness
      spec={{
        type: 'digit',
        validationError: 'Введите ровно одну цифру — например, 0 или 7.',
      }}
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/Введите одну цифру/)).toBeInTheDocument()
    await userEvent.type(canvas.getByLabelText('Ответ'), '17')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.tab()
    await expect(canvas.getByRole('alert')).toHaveTextContent('ровно одну цифру')
    await expect(canvas.getByLabelText('Ответ')).toHaveAttribute('aria-invalid', 'true')
  },
}

export const Tuple: Story = {
  name: 'Кортеж (три целых)',
  render: () => <Harness spec={{ type: 'int-3' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Число 1'), '1')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.type(canvas.getByLabelText('Число 2'), '7жф')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.type(canvas.getByLabelText('Число 3'), '9, 10')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.tab()
    await expect(canvas.getByRole('alert')).toHaveTextContent('три целых числа')
  },
}

export const PartialCompoundFormat: Story = {
  name: 'Составной формат · без преждевременной ошибки',
  render: () => <Harness label="Смешанная дробь" spec={{ type: 'mixed-fraction' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Смешанная дробь'), '1 2/')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.tab()
    await expect(canvas.getByRole('alert')).toHaveTextContent('смешанную дробь')
  },
}

export const Weekday: Story = {
  name: 'День недели · семь кнопок',
  render: () => <Harness spec={{ type: 'weekday' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const saturday = canvas.getByRole('button', { name: 'сб' })
    await userEvent.click(saturday)
    await expect(saturday).toHaveAttribute('aria-pressed', 'true')
    await expect(canvas.getByTestId('answer')).toHaveTextContent('сб')
  },
}

export const List: Story = {
  name: 'Список (последовательность целых)',
  render: () => <Harness spec={{ type: 'int-seq' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Ответ'), '1, 7, 9')
    // Предпросмотр появляется только после того же разбора, что использует legacy.
    await expect(canvas.getByText('Распознано:')).toBeInTheDocument()
    await expect(canvas.getByText('7')).toBeInTheDocument()
    await expect(canvas.getByTestId('answer')).toHaveTextContent('1, 7, 9')
  },
}

export const Choice: Story = {
  name: 'Выбор одного варианта',
  render: () => (
    <Harness
      label="Чётность числа"
      spec={{
        type: 'select-one',
        options: [
          { value: 'even', label: 'Чётное' },
          { value: 'odd', label: 'Нечётное' },
        ],
      }}
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('radio', { name: 'Нечётное' }))
    await expect(canvas.getByTestId('answer')).toHaveTextContent('Нечётное')
  },
}

const gallery: { label: string; spec: AnswerSpec }[] = [
  { label: 'Цифра', spec: { type: 'digit' } },
  { label: 'Натуральное', spec: { type: 'natural' } },
  { label: 'Целое', spec: { type: 'integer' } },
  { label: 'Отношение', spec: { type: 'ratio' } },
  { label: 'Дробь', spec: { type: 'fraction' } },
  { label: 'Смешанная дробь', spec: { type: 'mixed-fraction' } },
  { label: 'Десятичная дробь', spec: { type: 'float' } },
  { label: 'Число с точностью', spec: { type: 'float-eps' } },
  { label: 'Многочлен', spec: { type: 'polynomial' } },
  { label: 'Время', spec: { type: 'time' } },
  { label: 'Дата', spec: { type: 'date' } },
  { label: 'День недели', spec: { type: 'weekday' } },
  { label: 'Два целых', spec: { type: 'int-2' } },
  { label: 'Три целых', spec: { type: 'int-3' } },
  { label: 'Четыре целых', spec: { type: 'int-4' } },
  { label: 'Последовательность целых', spec: { type: 'int-seq' } },
  { label: 'Множество целых', spec: { type: 'int-set' } },
  { label: 'Последовательность дробей', spec: { type: 'frac-seq' } },
  { label: 'Мультимножество', spec: { type: 'multiset' } },
  { label: 'Символьное выражение', spec: { type: 'symb-expression' } },
  { label: 'Эквивалентное выражение', spec: { type: 'symb-equiv' } },
  {
    label: 'Выбор одного',
    spec: {
      type: 'select-one',
      options: [
        { value: 'yes', label: 'Да' },
        { value: 'no', label: 'Нет' },
      ],
    },
  },
  { label: 'Строка', spec: { type: 'string', example: 'Ответ словами' } },
]

export const Gallery: Story = {
  name: 'Галерея типов ответа',
  render: () => (
    <div className="grid max-w-3xl gap-6 sm:grid-cols-2">
      {gallery.map(({ label, spec }) => (
        <TestAnswer key={spec.type} label={label} spec={spec} />
      ))}
    </div>
  ),
}

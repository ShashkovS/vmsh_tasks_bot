import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { AnswerSpec } from './answer-spec'
import { TestAnswer } from './test-answer'

const meta = { title: 'Product/Test answer', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

function Harness({ spec, label }: { spec: AnswerSpec; label?: string }) {
  const [value, setValue] = useState('')
  return (
    <div className="max-w-sm space-y-3">
      <TestAnswer label={label} onChange={setValue} spec={spec} />
      <p className="text-small text-muted-foreground" role="status">
        Отправится: <span data-testid="answer">{value || '—'}</span>
      </p>
    </div>
  )
}

export const Scalar: Story = {
  name: 'Скаляр (натуральное число)',
  render: () => <Harness spec={{ type: 'natural' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/Введите натуральное число/)).toBeInTheDocument()
    await userEvent.type(canvas.getByLabelText('Ответ'), '179')
    await expect(canvas.getByTestId('answer')).toHaveTextContent('179')
  },
}

export const Tuple: Story = {
  name: 'Кортеж (три целых)',
  render: () => <Harness spec={{ type: 'int-3' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Число 1'), '1')
    await userEvent.type(canvas.getByLabelText('Число 2'), '7')
    await userEvent.type(canvas.getByLabelText('Число 3'), '9')
    await expect(canvas.getByTestId('answer')).toHaveTextContent('1, 7, 9')
  },
}

export const List: Story = {
  name: 'Список (последовательность целых)',
  render: () => <Harness spec={{ type: 'int-seq' }} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Ответ'), '1, 7, 9')
    // Живой предпросмотр разобранных элементов.
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
    await expect(canvas.getByTestId('answer')).toHaveTextContent('odd')
  },
}

const gallery: { label: string; spec: AnswerSpec }[] = [
  { label: 'Натуральное', spec: { type: 'natural' } },
  { label: 'Целое', spec: { type: 'integer' } },
  { label: 'Дробь', spec: { type: 'fraction' } },
  { label: 'Десятичная дробь', spec: { type: 'float' } },
  { label: 'Время', spec: { type: 'time' } },
  { label: 'Три целых', spec: { type: 'int-3' } },
  { label: 'Последовательность целых', spec: { type: 'int-seq' } },
  { label: 'Мультимножество', spec: { type: 'multiset' } },
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
